from __future__ import absolute_import
from builtins import str
from builtins import range
import sys, shutil, os
import regex as re
import shlex
from .common import default_movie, plain_exercise, table_analysis, indent_lines, \
    bibliography, fix_ref_section_chapter, cite_with_multiple_args2multiple_cites, \
    _CODE_BLOCK, _MATH_BLOCK, DEFAULT_ARGLIST, envir_delimiter_lines
from .doconce import INLINE_TAGS_SUBST, INLINE_TAGS
from .latex import fix_latex_command_regex
from .html import html_movie, html_table
from .pandoc import pandoc_ref_and_label, pandoc_index_bib, pandoc_quote, \
     language2pandoc, pandoc_quiz
from .misc import option, errwarn, _abort
from doconce import globals
from . import jupyter_execution

try:
    from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output
    from nbformat import writes
    from nbformat.v4 import nbformat
except ImportError:
    # Try old style of v4
    try:
        from IPython.nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook, new_output, writes
        from IPython.nbformat import writes
        from nbformat.v4 import nbformat
    except ImportError:
        errwarn('*** error: cannot do import nbformat.v4 or IPython.nbformat.v4. Try with IPython.nbformat.v3')

# Global variables
figure_encountered = False
movie_encountered = False
figure_files = []
movie_files = []
figure_labels = {}
html_encountered = False

# html code and corresponding regex (here for reusability)
img2ipynb = {
    'imgtag':
        ('\n<img src="{filename}" {opts}>'
         '<p style="font-size: 0.9em"><i>Figure {figure_number}: {caption}</i></p>'
         ),
    'imgtag_regex':
        r'<(\w+) src=[\\]"(.+)[\\]" .*>(?=[<|\\n])',
    'md':
        '\![{caption}]({filename})',
    'md_regex':
        r'\!\[(?:Figure )(\d+)\]\((.+)\)',
    'Image':
        'Image(%{keyword}="{filename}")\n',
    'Image_regex':
        'Image\((\w+)=(\w+)\)',
}


def ipynb_author(authors_and_institutions, auth2index,
                 inst2index, index2inst, auth2email):
    # Old code
    authors = []
    for author, i, e in authors_and_institutions:
        author_str = "new_author(name=u'%s'" % author
        if i is not None:
            author_str += ", affiliation=u'%s'" % ' and '.join(i)
        if e is not None:
            author_str += ", email=u'%s'" % e
        author_str += ')'
        authors.append(author_str)
    s ='authors = [%s]' % (', '.join(authors))
    # -----------------------------------------------------
    # New code: typeset as lines, but insert a comment so we
    # can convert back <!-- dom:AUTHOR: ... ->
    # Feb 2021: Not sure what was the use for these comments.
    # They insert an unwanted line between each author
    s = '\n'
    for author, i, e in authors_and_institutions:
        '''
        s += '<!-- dom:AUTHOR: ' + author
        if e is not None:
            s += ' Email:' + e
        if i is not None:
            s += ' at ' + ' & '.join(i)
        s += ' -->\n'
        # Add extra line between heading and first author
        s+= '<!-- Author: -->  \n_%s_' % (author)  
        '''
        # Write the authors
        s += '_%s_' % (author)
        if e is not None:
            s += ' (email: `%s`)' % e
        if i is not None:
            s += ', ' + ' and '.join(i)
        s += '  \n'
    return s

def ipynb_table(table):
    text = html_table(table)
    text += '\n'
    # Fix the problem that `verbatim` inside the table is not
    # typeset as verbatim (according to the ipynb translator rules)
    # in the GitHub Issue Tracker
    text = re.sub(r'`([^`]+?)`', '<code>\g<1></code>', text)
    return text

def ipynb_figure(m):
    """Format figures for the ipynb format

    Return json code to embed a figure in ipynb output. The syntax is
    `FIGURE:[filename[, options][, sidecap=BOOL][, frac=NUM]] [caption]`.
    Keywords: `sidecap` (default is False), `frac` (default is ),
    Options: `--html_figure_hrule`, --html_figure_caption`, `--html_responsive_figure_width`
    :param _regex.Match m: regex match object
    :return: json code
    :rtype: str
    """
    filename = m.group('filename').strip()
    caption = m.group('caption').strip().strip('"').strip("'")
    opts = m.group('options').strip()
    info = dict()

    # Process any inline figure opts
    if opts:
        info = shlex.split(opts)
        info = dict(s.strip(',').split('=') for s in info)
        # String of options
        opts = ' '.join(['%s="%s"' % (opt, value)
                         for opt, value in info.items()
                         if opt not in ['frac', 'sidecap']])

    # m.group() must be called before m.group('name')
    text = '<!-- dom:%s -->\n<!-- begin figure -->\n' % m.group()

    # Get some global vars
    global figure_files
    if not filename.startswith('http'):
        figure_files.append(filename)
    figure_number = len(figure_labels) + 1

    # Extract figure label
    label = None
    pattern = r' *label\{(.+?)\}'
    m_label = re.search(pattern, caption)
    if m_label:
        label = m_label.group(1).strip()
        caption = re.sub(pattern, '', caption)
        figure_labels[label] = figure_number
    if label is not None:
        text += '<div id="%s"></div>\n' % label

    display_method = option('ipynb_figure=', 'imgtag')
    if display_method == 'md':
        # Markdown image syntax for embedded image in text
        # (no control of size, then one must use HTML syntax)
        text += img2ipynb['md'].format(caption, filename)
    elif display_method == 'imgtag':
        # Plain <img tag, allows specifying the image size
        # Fix caption markup so it becomes html
        for tag in 'bold', 'emphasize', 'verbatim':
            caption = re.sub(INLINE_TAGS[tag], INLINE_TAGS_SUBST['html'][tag],
                             caption, flags=re.MULTILINE)
        text += img2ipynb['imgtag'].format(filename=filename,
                                           opts=opts,
                                           caption=caption,
                                           figure_number=figure_number)
    elif display_method == 'Image':
        # Image object
        # NOTE: This code will normally not work because it inserts a verbatim
        # block in the file *after* all such blocks have been removed and
        # numbered. doconce.py makes a test prior to removal of blocks and
        # runs the handle_figures and movie substitution if ipynb format
        # and Image or movie object display.
        text += '\n<!-- options: %s -->\n' % opts
        text = '!bc pycod\n'
        global figure_encountered
        if not figure_encountered:
            # First time we have a figure, we must import Image
            text += 'from IPython.display import Image\n'
            figure_encountered = True
        if caption:
            text += '# ' + caption
        if filename.startswith('http'):
            keyword = 'url'
        else:
            keyword = 'filename'
        text += img2ipynb['Image'].format(keyword, filename)
        text += '!ec\n'
    else:
        errwarn('*** error: --ipynb_figure=%s is illegal, must be md, imgtag or Image' % display_method)
        _abort()
    text += '\n<!-- end figure -->\n'
    return text

def ipynb_movie(m):
    # m.group() must be called before m.group('name')
    text = '<!-- dom:%s -->' % m.group()

    global html_encountered, movie_encountered, movie_files
    filename = m.group('filename')
    caption = m.group('caption').strip()
    youtube = False

    if 'youtu.be' in filename or 'youtube.com' in filename:
        youtube = True
    if '*' in filename or '->' in filename:
        errwarn('*** warning: * or -> in movie filenames is not supported in ipynb')
        return text

    def YouTubeVideo(filename):
        # Use YouTubeVideo object
        if 'watch?v=' in filename:
            name = filename.split('watch?v=')[1]
        elif 'youtu.be/' in filename:
            name = filename.split('youtu.be/')[1]
        else:
            errwarn('*** error: youtube movie name "%s" could not be interpreted' % filename)
            _abort()

        text = ''
        global movie_encountered
        if not movie_encountered:
            text += 'from IPython.display import YouTubeVideo\n'
            movie_encountered = True
        text += 'YouTubeVideo("%s")\n' % name
        return text

    text += '\n<!-- begin movie -->\n'
    display_method = option('ipynb_movie=', 'HTML')
    if display_method == 'md':
        text += html_movie(m)
    elif display_method.startswith('HTML'):
        text += '\n!bc pycod\n'
        if youtube and 'YouTube' in display_method:
            text += YouTubeVideo(filename)
            if caption:
                text += '\nprint("%s" % caption)'
        else:
            # Use HTML formatting
            if not html_encountered:
                text += 'from IPython.display import HTML\n'
                html_encountered = True
            text += '_s = """' + html_movie(m) + '"""\n'
            text += 'HTML(_s)\n'
            if not filename.startswith('http'):
                movie_files.append(filename)
        text += '!ec\n'
    elif display_method == 'ipynb':
        text += '!bc pycod\n'
        if youtube:
            text += YouTubeVideo(filename)
            if caption:
                text += '\nprint("%s" % caption)'
        else:
            # see https://nbviewer.ipython.org/github/ipython/ipython/blob/1.x/examples/notebooks/Part%205%20-%20Rich%20Display%20System.ipynb
            # https://stackoverflow.com/questions/18019477/how-can-i-play-a-local-video-in-my-ipython-notebook
            # https://python.6.x6.nabble.com/IPython-User-embedding-non-YouTube-movies-in-the-IPython-notebook-td5024035.html
            # Just support .mp4, .ogg, and.webm
            stem, ext = os.path.splitext(filename)
            if ext not in ('.mp4', '.ogg', '.webm'):
                errwarn('*** error: movie "%s" in format %s is not supported for --ipynb_movie=%s' % (filename, ext, display_method))
                errwarn('    use --ipynb_movie=HTML instead')
                _abort()
            height = 365
            width = 640
            if filename.startswith('http'):
                file_open = 'import urllib\nvideo = urllib.urlopen("%s").read()' % filename
            else:
                file_open = 'video = open("%s", "rb").read()' % filename
            text += ('%s'
                     'from base64 import b64encode'
                     'video_encoded = b64encode(video)'
                     'video_tag = \'<video controls loop alt="%s" height="%s" width="%s" src="data:video/%s;base64,{0}">\'.format(video_encoded)'
                     ) % (file_open, filename, height, width, ext[1:])
            if not filename.startswith('http'):
                movie_files.append(filename)
            if not html_encountered:
                text += 'from IPython.display import HTML\n'
                html_encountered = True
            text += 'HTML(data=video_tag)\n'
            if caption:
                text += '\nprint("%s" % caption)'
        text += '!ec\n'
    else:
        errwarn('*** error: --ipynb_movie=%s is not supported' % display_method)
        _abort()
    text += '<!-- end movie -->\n'
    return text

def ipynb_code(filestr, code_blocks, code_block_types,
               tex_blocks, format):
    """
    # We expand all newcommands now
    from html import embed_newcommands
    newcommands = embed_newcommands(filestr)
    if newcommands:
        filestr = newcommands + filestr
    """
    # Prepend the doconce command
    intro = ('HTML file automatically generated from DocOnce source (https://github.com/doconce/doconce/)\n'
             'doconce format html %s %s') % (globals.filename, ' '.join(sys.argv[1:]))
    filestr = INLINE_TAGS_SUBST[format]['comment'] % intro + '\n' + filestr
    # Fix pandoc citations to normal internal links: [[key]](#key)
    filestr = re.sub(r'\[@(.+?)\]', r'[[\g<1>]](#\g<1>)', filestr)

    # filestr becomes json list after this function so we must typeset
    # envirs here. All envirs are typeset as pandoc_quote.
    envir_format = option('ipynb_admon=', 'paragraph')
    # Remove all !bpop-!epop environments (they cause only problems and
    # have no use)
    for envir in 'pop', 'slidecell':
        filestr = re.sub('^<!-- !b%s .*\n' % envir, '', filestr,
                         flags=re.MULTILINE)
        filestr = re.sub('^<!-- !e%s .*\n' % envir, '', filestr,
                         flags=re.MULTILINE)
    filestr = re.sub('^<!-- !bnotes.*?<!-- !enotes -->\n', '', filestr,
                     flags=re.DOTALL|re.MULTILINE)
    #filestr = re.sub('^<!-- !split -->\n', '', filestr, flags=re.MULTILINE)

    # NB: some of the following environments might have already been processed
    envirs = globals.doconce_envirs[8:-2]
    for envir in envirs:
        pattern = r'^!b%s(.*?)\n(.+?)\s*^!e%s' % (envir, envir)
        if envir_format in ('quote', 'paragraph', 'hrule'):
            def subst(m):
                title = m.group(1).strip()
                # Text size specified in parenthesis?
                m2 = re.search('^\s*\((.+?)\)', title)

                if title == '' and envir not in ('block', 'quote'):
                    title = envir.capitalize() + '.'
                elif title.lower() == 'none':
                    title == ''
                elif m2:
                    text_size = m2.group(1).lower()
                    title = title.replace('(%s)' % text_size, '').strip()
                elif title and title[-1] not in ('.', ':', '!', '?'):
                    # Make sure the title ends with puncuation
                    title += '.'
                # Recall that this formatting is called very late
                # so native format must be used!
                if title:
                    title = '**' + title + '**\n'
                    # Could also consider subsubsection formatting
                block = m.group(2)

                # Always use quote typesetting for quotes
                if envir_format == 'quote' or envir == 'quote':
                    # Make Markdown quote of the block: lines start with >
                    lines = []
                    for line in block.splitlines():
                        # Just quote plain text
                        if not (_MATH_BLOCK in line or
                                _CODE_BLOCK in line or
                                line.startswith('FIGURE:') or
                                line.startswith('MOVIE:') or
                                line.startswith('|')):
                            lines.append('> ' + line)
                        else:
                            lines.append('\n' + line + '\n')
                    block = '\n'.join(lines) + '\n\n'

                    # Add quote and a blank line after title
                    if title:
                        title = '> ' + title + '>\n'
                else:
                    # Add a blank line after title
                    if title:
                        title += '\n'

                if envir_format == 'hrule':
                    # Native ------ does not work, use <hr/>
                    #text = '\n\n----------\n' + title + '----------\n' + \
                    #       block + '\n----------\n\n'
                    text = '\n\n<hr/>\n' + title + \
                           block + '\n<hr/>\n\n'
                else:
                    text = title + block + '\n\n'
                return text
        else:
            errwarn('*** error: --ipynb_admon=%s is not supported'  % envir_format)
        filestr = re.sub(pattern, subst, filestr,
                         flags=re.DOTALL | re.MULTILINE)

    # Fix pyshell and ipy interactive sessions: remove prompt and output.
    # or split in multiple cells such that output comes out at the end of a cell
    # Fix sys environments and use run prog.py so programs can be run in cell
    # Insert %matplotlib inline in the first block using matplotlib
    # Only typeset Python code as blocks, otherwise !bc environmens
    # become plain indented Markdown.
    ipynb_tarfile = 'ipynb-%s-src.tar.gz' % globals.dofile_basename
    src_paths = set()
    mpl_inline = False

    # allow the user to disable automatic insertion of `%matplotlib inline`
    disable_mpl_inline = option('ipynb_disable_mpl_inline', False)
    if disable_mpl_inline:
        mpl_inline = True

    split_pyshell = option('ipynb_split_pyshell=', 'on')
    if split_pyshell is None:
        split_pyshell = False
    elif split_pyshell in ('no', 'False', 'off'):
        split_pyshell = False
    else:
        split_pyshell = True

    ipynb_code_tp = [None]*len(code_blocks)
    for i in range(len(code_blocks)):
        # Check if continuation lines are in the code block, because
        # doconce.py inserts a blank after the backslash
        if '\\ \n' in code_blocks[i]:
            code_blocks[i] = code_blocks[i].replace('\\ \n', '\\\n')

        if not mpl_inline and (
            re.search(r'import +matplotlib', code_blocks[i]) or \
            re.search(r'from +matplotlib', code_blocks[i]) or \
            re.search(r'import +scitools', code_blocks[i]) or \
            re.search(r'from +scitools', code_blocks[i])):
            code_blocks[i] = '%matplotlib inline\n\n' + code_blocks[i]
            mpl_inline = True

        tp = code_block_types[i]
        if tp.endswith('-t'):
            # Standard Markdown code with pandoc/github extension
            language = tp[:-2]
            language_spec = language2pandoc.get(language, '')
            #code_blocks[i] = '\n' + indent_lines(code_blocks[i], format) + '\n'
            code_blocks[i] = "```%s\n" % language_spec + \
                             indent_lines(code_blocks[i].strip(), format) + \
                             "```"
            ipynb_code_tp[i] = 'markdown'
        elif tp.startswith('pyshell') or tp.startswith('ipy'):
            lines = code_blocks[i].splitlines()
            last_cell_end = -1
            if split_pyshell:
                new_code_blocks = []
                # Split for each output an put in separate cell
                for j in range(len(lines)):
                    if lines[j].startswith('>>>') or lines[j].startswith('... '):
                        lines[j] = lines[j][4:]
                    elif lines[j].startswith('In ['):  # IPython
                        lines[j] = ':'.join(lines[j].split(':')[1:]).strip()
                    elif lines[j].startswith('   ...: '): # IPython
                        lines[j] = lines[j][8:]
                    else:
                        # output (no prefix or Out)
                        lines[j] = ''
                        new_code_blocks.append(
                            '\n'.join(lines[last_cell_end+1:j+1]))
                        last_cell_end = j
                code_blocks[i] = new_code_blocks
                ipynb_code_tp[i] = 'cell'
            else:
                # Remove prompt and output lines; leave code executable in cell
                for j in range(len(lines)):
                    if lines[j].startswith('>>> ') or lines[j].startswith('... '):
                        lines[j] = lines[j][4:]
                    elif lines[j].startswith('In ['):
                        lines[j] = ':'.join(lines[j].split(':')[1:]).strip()
                    else:
                        # output
                        lines[j] = ''

                for j in range(lines.count('')):
                    lines.remove('')
                code_blocks[i] = '\n'.join(lines)
                ipynb_code_tp[i] = 'cell'
        elif tp.startswith('sys'):
            # Do we find execution of python file? If so, copy the file
            # to separate subdir and make a run file command in a cell.
            # Otherwise, it is just a plain verbatim Markdown block.
            found_unix_lines = False
            lines = code_blocks[i].splitlines()
            for j in range(len(lines)):
                m = re.search(r'(.+?>|\$) *python +([A-Za-z_0-9]+?\.py)',
                              lines[j])
                if m:
                    name = m.group(2).strip()
                    if os.path.isfile(name):
                        src_paths.add(os.path.dirname(name))
                        lines[j] = '%%run "%s"' % name
                else:
                    found_unix_lines = True
            src_paths = list(src_paths)
            if src_paths and not found_unix_lines:
                # This is a sys block with run commands only
                code_blocks[i] = '\n'.join(lines)
                ipynb_code_tp[i] = 'cell'
            else:
                # Standard Markdown code
                code_blocks[i] = '\n'.join(lines)
                code_blocks[i] = indent_lines(code_blocks[i], format)
                ipynb_code_tp[i] = 'markdown'
        elif tp.endswith("-e"):
            ipynb_code_tp[i] = 'cell_execute_hidden'
        elif tp.endswith('hid'):
            ipynb_code_tp[i] = 'cell_hidden'
        elif tp.endswith('out'):
            ipynb_code_tp[i] = 'cell_output'
        elif tp.startswith('py'):
            ipynb_code_tp[i] = 'cell'
        else:
            # Should support other languages as well, but not for now
            code_blocks[i] = indent_lines(code_blocks[i], format)
            ipynb_code_tp[i] = 'markdown'

    # figure_files and movie_files are global variables and contain
    # all figures and movies referred to
    src_paths = list(src_paths)
    if figure_files:
        src_paths += figure_files
    if movie_files:
        src_paths += movie_files

    if src_paths:
        # Make tar file with all the source dirs with files
        # that need to be executed
        os.system('tar cfz %s %s' % (ipynb_tarfile, ' '.join(src_paths)))
        errwarn('collected all required additional files in ' + ipynb_tarfile + ' which must be distributed with the notebook')
    elif os.path.isfile(ipynb_tarfile):
        os.remove(ipynb_tarfile)

    # Parse document into markdown text, code blocks, and tex blocks.
    # Store in nested list notebook_blocks.
    # Also remove some commented markers
    notebook_blocks = [[]]
    marker_subex_begin = INLINE_TAGS_SUBST[format]['comment'] % envir_delimiter_lines['subex'][0]
    markers2rm = []
    markers2rm.append(INLINE_TAGS_SUBST[format]['comment'] % envir_delimiter_lines['subex'][1])
    markers2rm.append(INLINE_TAGS_SUBST[format]['comment'] % envir_delimiter_lines['exercise'][0])
    markers2rm.append(INLINE_TAGS_SUBST[format]['comment'] % envir_delimiter_lines['exercise'][1])
    for line in filestr.splitlines():
        if line == '':
            notebook_blocks[-1].append('\n')
        elif line.startswith('#'):
            # Each chapter, sub/sub/section in its own cell
            notebook_blocks.append([])
            notebook_blocks[-1].append(line)
        elif line in marker_subex_begin:
            # Each subex in its own cell
            notebook_blocks.append([])
        elif line in markers2rm:
            # Remove the markers for begin/end of exercises and subexercises
            notebook_blocks[-1].append('\n')
        elif _CODE_BLOCK in line:
            code_block_tp = line.split()[-1]
            if code_block_tp in ('pyhid',) or not code_block_tp.endswith('hid'):
                notebook_blocks.append([line])
                notebook_blocks.append([])
        elif _MATH_BLOCK in line:
            notebook_blocks.append([line])
            notebook_blocks.append([])
        elif '!split' in line:
            # !split starts a new exercise (therefore it cannot be placed between subex, sol, ans, etc)
            notebook_blocks.append([])
        elif envir_delimiter_lines['subex'][0] in line:
            notebook_blocks[-1] = '\n'.join(notebook_blocks[-1]).strip()
            notebook_blocks.append([])
        else:
            notebook_blocks[-1].append(line)
    # Join text in each element of notebook_blocks removing multiple newlines
    for i, block in enumerate(notebook_blocks):
        block = '\n'.join(block).strip()
        notebook_blocks[i] = re.sub(r'\n\n+','\n\n', block)
    # Remove empty blocks
    notebook_blocks = [b for b in notebook_blocks if b != '']

    # Add block type info
    pattern = r'(\d+) +%s'
    for i in range(len(notebook_blocks)):
        if re.match(pattern % _CODE_BLOCK, notebook_blocks[i]):
            m = re.match(pattern % _CODE_BLOCK, notebook_blocks[i])
            idx = int(m.group(1))
            if ipynb_code_tp[idx].startswith('cell'):
                notebook_blocks[i] = [ipynb_code_tp[idx], notebook_blocks[i]]
            else:
                notebook_blocks[i] = ['text', notebook_blocks[i]]
        elif re.match(pattern % _MATH_BLOCK, notebook_blocks[i]):
            notebook_blocks[i] = ['math', notebook_blocks[i]]
        else:
            notebook_blocks[i] = ['text', notebook_blocks[i]]

    # Go through tex_blocks and wrap math blocks in $$
    # (doconce.py runs align2equations so there are no align/align*
    # environments in tex blocks)
    label2tag = {}
    tag_counter = 1
    for i in range(len(tex_blocks)):
        # Extract labels and add tags
        labels = re.findall(r'label\{(.+?)\}', tex_blocks[i])
        for label in labels:
            label2tag[label] = tag_counter
            # Insert tag to get labeled equation
            tex_blocks[i] = tex_blocks[i].replace(
                'label{%s}' % label, 'label{%s} \\tag{%s}' % (label, tag_counter))
            tag_counter += 1

        # Remove \[ and \] or \begin/end{equation*} in single equations
        tex_blocks[i] = tex_blocks[i].replace(r'\[', '')
        tex_blocks[i] = tex_blocks[i].replace(r'\]', '')
        tex_blocks[i] = tex_blocks[i].replace(r'\begin{equation*}', '')
        tex_blocks[i] = tex_blocks[i].replace(r'\end{equation*}', '')
        # Check for illegal environments
        m = re.search(r'\\begin\{(.+?)\}', tex_blocks[i])
        if m:
            envir = m.group(1)
            if envir not in ('equation', 'equation*', 'align*', 'align',
                             'array'):
                errwarn(
                    ('\n*** warning: latex envir \\begin{%s} does not work well in Markdown.'
                    '    Stick to \\[ ... \\], equation, equation*, align, or align*'
                    '    environments in math environments.') % envir)

        eq_type = 'heading'  # or '$$'
        eq_type = '$$'
        # Markdown: add $$ on each side of the equation
        if eq_type == '$$':
            # Make sure there are no newline after equation
            tex_blocks[i] = '$$\n' + tex_blocks[i].strip() + '\n$$'
        # Here: use heading (###) and simple formula (remove newline
        # in math expressions to keep everything within a heading) as
        # the equation then looks bigger
        elif eq_type == 'heading':
            tex_blocks[i] = '### $ ' + '  '.join(tex_blocks[i].splitlines()) + ' $'

        # Add labels for the eqs above the block (for reference)
        if labels:
            #label_tp = '<a name="%s"></a>'
            label_tp = '<div id="%s"></div>'
            tex_blocks[i] = '<!-- Equation labels as ordinary links -->\n' + \
                            ' '.join([label_tp % label
                                      for label in labels]) + '\n\n' + \
                                      tex_blocks[i]

    # blocks is now a list of text chunks in markdown and math/code line
    # instructions. Insert code and tex blocks
    for i in range(len(notebook_blocks)):
        if _CODE_BLOCK in notebook_blocks[i][1] or _MATH_BLOCK in notebook_blocks[i][1]:
            words = notebook_blocks[i][1].split()
            # start of notebook_blocks[i]: number block-indicator code-type
            n = int(words[0])
            if _CODE_BLOCK in notebook_blocks[i][1]:
                notebook_blocks[i][1] = code_blocks[n]  # can be list!
            if _MATH_BLOCK in notebook_blocks[i][1]:
                notebook_blocks[i][1] = tex_blocks[n]

    global new_code_cell, new_markdown_cell, new_notebook, new_output
    cells = []              # ipynb cells
    mdstr = []              # plain md format of the notebook
    execution_count = 1
    kernel_client = None    # Placeholder for a JupyterKernelClient instance
    if option("execute"):
        kernel_client = jupyter_execution.JupyterKernelClient(syntax='python')
    editable_md = True      # Metadata for md text
    if option('ipynb_non_editable_text'):
        editable_md = False

    for block_tp, block in notebook_blocks:
        if (block_tp == 'text' or block_tp == 'math') and block != '' and block != '<!--  -->':
            block = re.sub(r"caption\{(.*)\}", r"*Figure: \1*", block)
            cells.append(new_markdown_cell(source=block, metadata=dict(editable=editable_md)))
            mdstr.append(('markdown', block))
        elif block_tp == 'cell_output' and block != '' and not option("ignore_output"):
            # Process cells with block type cell_output (*out)
            block = block.rstrip()
            outputs = [
                new_output(
                    output_type="execute_result",
                    data={
                        "text/plain": [
                            block
                          ]
                    },
                    execution_count=execution_count-1
                )
            ]
            previous_cell = cells[-1]
            if previous_cell.cell_type == "code":
                previous_cell.outputs = outputs
            else:
                print("WARNING: DocOnce ipynb got code output,",
                      "but previous was not code.")
                cell = new_code_cell(
                    source="#",
                    outputs=outputs,
                    execution_count=execution_count,
                    metadata=dict(collapsed=False)
                )
                cells.append(cell)
                mdstr.append(('codecell', block))
        elif block_tp.startswith('cell'):
            # Process cells with block type cell (py*), cell_execute_hidden (*-e), cell_hidden (*hid)
            execution_count, md_out = process_ipynb_code_block(kernel_client, block, block_tp, cells, execution_count)
            mdstr.extend(md_out)

    nb = new_notebook(cells=cells)
    filestr = writes(nb, version=4)

    # Check that there are no empty cells:
    if '"input": []' in filestr:
        errwarn('*** error: empty cells in notebook - report bug in DocOnce')
        _abort()
    # must do the replacements here at the very end when json is written out
    # \eqref and labels will not work, but labels (only in math) do no harm
    filestr = re.sub(r'([^\\])label\{', r'\g<1>\\\\label{', filestr,
                     flags=re.MULTILINE)
    # \\eqref{} just gives (???) link at this stage - future versions
    # will probably support labels
    #filestr = re.sub(r'\(ref\{(.+?)\}\)', r'\\eqref{\g<1>}', filestr)
    # Now we use explicit references to tags
    def subst(m):
        label = m.group(1)
        try:
            return r'[(%s)](#%s)' % (label2tag[label], label)
        except KeyError as e:
            errwarn('*** error: label "%s" is not defined' % str(e))

    #filestr = re.sub(r'\(ref\{(.+?)\}\)', subst, filestr)

    # pandoc_ref_and_label replaces ref{%s} with [%s](#%s), where label is inserted
    # we want the link to display the equation number instead of the label
    for label, tag in label2tag.items():
        filestr = filestr.replace("[%s](#%s)" % (label, label), "[%s](#%s)" % (tag, label))

    """
    # MathJax reference to tag (recall that the equations have both label
    # and tag (know that tag only works well in HTML, but this mjx-eqn-no
    # label does not work in ipynb)
    filestr = re.sub(r'\(ref\{(.+?)\}\)',
                     lambda m: r'[(%s)](#mjx-eqn-%s)' % (label2tag[m.group(1)], label2tag[m.group(1)]), filestr)
    """
    #filestr = re.sub(r'\(ref\{(.+?)\}\)', r'Eq (\g<1>)', filestr)

    '''
    # Final fixes: replace all text between cells by markdown code cells
    # Note: the patterns are overlapping so a plain re.sub will not work,
    # here we run through all blocks found and subsitute the first remaining
    # one, one by one.
    pattern = r'   \},\n(.+?)\{\n    "cell_type":'
    begin_pattern = r'^(.+?)\{\n    "cell_type":'
    remaining_block_begin = re.findall(begin_pattern, filestr, flags=re.DOTALL)
    remaining_blocks = re.findall(pattern, filestr, flags=re.DOTALL)
    import string
    for block in remaining_block_begin + remaining_blocks:
        filestr = string.replace(filestr, block, json_markdown(block) + '   ',
                                 maxreplace=1)
    filestr_end = re.sub(r'   \{\n    "cell_type": .+?\n   \},\n', '', filestr,
                         flags=re.DOTALL)
    filestr = filestr.replace(filestr_end, json_markdown(filestr_end))
    filestr = ('{'
               '  "metadata": {'
               '    "name": "SOME NAME"'
               '  },'
               '  "nbformat": 3,'
               '  "nbformat_minor": 0,'
               '  "worksheets": ['
               '    {'
               '      "cells": [') + \
              filestr.rstrip() + '\n'+ \
              json_pycode('', final_prompt_no+1, 'python').rstrip()[:-1] + \
              (''
               '        ],'
               '      "metadata": {}'
               '    }'
               '  ]'
               '}')
    '''
    if option("execute"):
        kernel_client.stop()

    return filestr


def process_ipynb_code_block(kernel_client, block, block_tp, cells, execution_count):
    md_out = []
    editable = True
    collapsed = False
    if option('ipynb_non_editable_code'):
        editable=False
    if block_tp == 'cell_hidden':
        collapsed = True
    # Start processing the block
    if not isinstance(block, list):
        block = [block]
    for blockline in block:
        blockline = blockline.rstrip()
        if blockline == '': continue
        cell = new_code_cell(
            source=blockline,
            execution_count=execution_count,
            metadata=dict(editable=editable, collapsed=collapsed)
        )
        if block_tp != 'cell_execute_hidden':
            cells.append(cell)
        if option("execute"):
            outputs, execution_count_out = kernel_client.run_cell(blockline)
            cell.outputs = outputs
            if execution_count_out:
                cell["execution_count"] = execution_count_out
        execution_count += 1
        md_out.append(('codecell', blockline))
    return execution_count, md_out


def ipynb_index_bib(filestr, index, citations, pubfile, pubdata):
    # ipynb has support for latex-style bibliography.
    # Quite some code here is copy from latex_index_bib
    # https://nbviewer.ipython.org/github/ipython/nbconvert-examples/blob/master/citations/Tutorial.ipynb
    if citations:
        filestr = cite_with_multiple_args2multiple_cites(filestr)
    for label in citations:
        filestr = filestr.replace('cite{%s}' % label,
                                  '<cite data-cite="%s">[%d]</cite>' %
                                  (label, citations[label]))

    if pubfile is not None:
        # Always produce a new bibtex file
        bibtexfile = pubfile[:-3] + 'bib'
        errwarn('\nexporting publish database %s to %s:' % (pubfile, bibtexfile))
        publish_cmd = 'publish export %s' % os.path.basename(bibtexfile)
        # Note: we have to run publish in the directory where pubfile resides
        this_dir = os.getcwd()
        pubfile_dir = os.path.dirname(pubfile)
        if not pubfile_dir:
            pubfile_dir = os.curdir
        os.chdir(pubfile_dir)
        os.system(publish_cmd)
        os.chdir(this_dir)

        bibstyle = option('latex_bibstyle=', 'plain')
        bibtext = fix_latex_command_regex((
            "((*- extends 'latex_article.tplx' -*))"
            ''
            '((* block bibliography *))'
            r'\bibliographystyle{%s}'
            r'\bibliography{%s}'
            '((* endblock bibliography *))'
        ) % (bibstyle, bibtexfile[:-4]), application='replacement')
        filestr = re.sub(r'^BIBFILE:.+$', bibtext, filestr,
                         flags=re.MULTILINE)

    # Save idx{} and label{} as metadata, also have labels as div tags
    filestr = re.sub(r'(idx\{.+?\})', r'<!-- dom:\g<1> -->', filestr)
    filestr = re.sub(r'(label\{(.+?)\})', r'<!-- dom:\g<1> --><div id="\g<2>"></div>', filestr)
    # Also treat special cell delimiter comments that might appear from
    # doconce ipynb2doconce conversions
    filestr = re.sub(r'^# ---------- (markdown|code) cell$', '',
                     filestr, flags=re.MULTILINE)
    return filestr

def ipynb_index_bib_latex_plain(filestr, index, citations, pubfile, pubdata):
    if citations:
        filestr = cite_with_multiple_args2multiple_cites(filestr)

    for label in citations:
        filestr = filestr.replace('cite{%s}' % label,'[[{}]](#{})'.format(citations[label], label))

    if pubfile is not None:
        bibtext = bibliography(pubdata, citations, format='ipynb')
        filestr = re.sub(r'^BIBFILE:.+$', bibtext, filestr, flags=re.MULTILINE)
    # remove all index entries (could also place them
    # in special comments to keep the information)
    filestr = re.sub(r'idx\{.+?\}' + '\n?', '', filestr)

    # Use HTML anchors for labels and [link text](#label) for references
    # outside mathematics.
    #filestr = re.sub(r'label\{(.+?)\}', '<a name="\g<1>"></a>', filestr)
    # Note: HTML5 should have <sometag id="..."></sometag> instead
    #filestr = re.sub(r'label\{(.+?)\}', '<div id="\g<1>"></div>', filestr)
    # Use <span> instead of <div>. Unlike block-level HTML tags (<div>),
    # Markdown does get processed within span-level tags as <span>.
    filestr = re.sub(r'label\{(.+?)\}', '<span id="\g<1>"></span>', filestr)

    return filestr


def ipynb_ref_and_label(section_label2title, format, filestr):
    filestr = fix_ref_section_chapter(filestr, format)

    # Replace all references to sections. Pandoc needs a coding of
    # the section header as link. (Not using this anymore.)
    def title2pandoc(title):
        # https://johnmacfarlane.net/pandoc/README.html
        for c in ('?', ';', ':'):
            title = title.replace(c, '')
        title = title.replace(' ', '-').strip()
        start = 0
        for i in range(len(title)):
            if title[i].isalpha():
                start = i
        title = title[start:]
        title = title.lower()
        if not title:
            title = 'section'
        return title

    for label in section_label2title:
        filestr = filestr.replace('ref{%s}' % label,
                  '[%s](#%s)' % (section_label2title[label],
                                 label))

    # TODO Consider handling the case where a figure label is used
    # but not referenced as "figure ref{label}"

    pattern = r'([Ff]igure|[Mm]ovie)\s+ref\{(.+?)\}'
    for m in re.finditer(pattern, filestr):
        label = m.group(2).strip()
        try:
            figure_number = figure_labels[label]
            replace_pattern = r'([Ff]igure|[Mm]ovie)\s+ref\{' + label + r'\}'
            replace_string = '[\g<1> {figure_number}](#{label})'.format(
            figure_number=figure_number,
            label=label
            )
            filestr = re.sub(replace_pattern, replace_string, filestr)
        except KeyError:
            errwarn("*** warning: Missing figure label '{}'".format(label))

    # Remaining ref{} (should protect \eqref)
    filestr = re.sub(r'ref\{(.+?)\}', '[\g<1>](#\g<1>)', filestr)
    return filestr


def define(FILENAME_EXTENSION,
           BLANKLINE,
           INLINE_TAGS_SUBST,
           CODE,
           LIST,
           ARGLIST,
           TABLE,
           EXERCISE,
           FIGURE_EXT,
           CROSS_REFS,
           INDEX_BIB,
           TOC,
           ENVIRS,
           QUIZ,
           INTRO,
           OUTRO,
           filestr):
    # all arguments are dicts and accept in-place modifications (extensions)

    FILENAME_EXTENSION['ipynb'] = '.ipynb'
    BLANKLINE['ipynb'] = '\n'
    # replacement patterns for substitutions of inline tags
    INLINE_TAGS_SUBST['ipynb'] = {
        'math':      None,  # indicates no substitution, leave as is
        'math2':     r'\g<begin>$\g<latexmath>$\g<end>',
        'emphasize': None,
        'bold':      r'\g<begin>**\g<subst>**\g<end>',
        'figure':    ipynb_figure,
        'movie':     ipynb_movie,
        'verbatim':  None,
        #'linkURL':   r'\g<begin>\g<link> (\g<url>)\g<end>',
        'linkURL2':  r'[\g<link>](\g<url>)',
        'linkURL3':  r'[\g<link>](\g<url>)',
        'linkURL2v': r'[`\g<link>`](\g<url>)',
        'linkURL3v': r'[`\g<link>`](\g<url>)',
        'plainURL':  r'<\g<url>>',
        'colortext': r'<font color="\g<color>">\g<text></font>',
        'title':     r'<!-- dom:TITLE: \g<subst> -->\n# \g<subst>',
        'author':    ipynb_author,
        'date':      '\nDate: _\g<subst>_\n',
        'chapter':       lambda m: '# '   + m.group('subst'),  # seldom used in notebooks
        'section':       lambda m: '# '   + m.group('subst'),
        'subsection':    lambda m: '## '  + m.group('subst'),
        'subsubsection': lambda m: '### ' + m.group('subst') + '\n',
        'paragraph':     r'**\g<subst>**\g<space>',
        'abstract':      r'\n**\g<type>.** \g<text>\n\n\g<rest>',
        'comment':       '<!-- %s -->',
        'linebreak':     r'\g<text>',  # Not sure how this is supported; Markdown applies <br> but that cannot be used for latex output with ipynb...
        'non-breaking-space': ' ',
        'ampersand2':    r' \g<1>&\g<2>',
        }

    CODE['ipynb'] = ipynb_code
    # Envirs are in doconce.py treated after code is inserted, which
    # means that the ipynb format is json. Therefore, we need special
    # treatment of envirs in ipynb_code and ENVIRS can be empty.
    ENVIRS['ipynb'] = {}

    ARGLIST['ipynb'] = DEFAULT_ARGLIST
    LIST['ipynb'] = {
        'itemize':
        {'begin': '', 'item': '*', 'end': '\n'},

        'enumerate':
        {'begin': '', 'item': '%d.', 'end': '\n'},

        'description':
        {'begin': '', 'item': '%s\n  :   ', 'end': '\n'},

        'separator': '\n',
        }
    CROSS_REFS['ipynb'] = ipynb_ref_and_label

    TABLE['ipynb'] = ipynb_table
    cite = option('ipynb_cite=', 'plain')
    if cite == 'latex':
        INDEX_BIB['ipynb'] = ipynb_index_bib
    elif cite == 'latex-plain':
        INDEX_BIB['ipynb'] = ipynb_index_bib_latex_plain
    else:
        INDEX_BIB['ipynb'] = pandoc_index_bib
    EXERCISE['ipynb'] = plain_exercise
    TOC['ipynb'] = lambda s, f: ''
    FIGURE_EXT['ipynb'] = {
        'search': ('.png', '.gif', '.jpg', '.jpeg', '.tif', '.tiff'),
        'convert': ('.png', '.gif', '.jpg')}
    QUIZ['ipynb'] = pandoc_quiz
