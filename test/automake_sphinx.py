#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Autogenerated file (by doconce sphinx_dir).
# Purpose: create HTML Sphinx version of document "tmp_copyright".
#
# Note: doconce clean removes this file, so if you edit the file,
# rename it to avoid automatic removal.

# To force compilation of the doconce file to sphinx format, remove
# the sphinx (.rst) file first.
#
# Command-line arguments are transferred to the "doconce format sphinx"
# compilation command.
#

import glob, sys, os, subprocess, shutil, logging
logging.basicConfig(
    filename='automake_sphinx.log', filemode='w', level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y.%m.%d %I:%M:%S %p')


command_line_options = ' '.join(['"%s"' % arg for arg in sys.argv[1:]])

sphinx_rootdir = 'tmp_sphinx-rootdir4'
source_dir = sphinx_rootdir

if not os.path.isdir(sphinx_rootdir):
    print("""*** error: %(sphinx_rootdir)s does not exist. This means unsuccessful
    doconce sphinx_dir command. Try to upgrade to latest DocOnce version.
    (The script tmp_sphinx_gen.sh runs sphinx-quickstart - it may have failed.)
""" % vars())
    sys.exit(1)

def system(cmd, capture_output=False, echo=True):
    if echo:
        print('running', cmd)
    if capture_output:
        failure, outtext = subprocess.getstatusoutput(cmd) # Unix/Linux only
    else:
        failure = os.system(cmd)
    if failure:
        print('Could not run', cmd)
        logging.critical('Could not run %s' % cmd)
        sys.exit(1)
    if capture_output:
        return outtext

# Copy generated sphinx files to sphinx root directory
filename = 'tmp_copyright'
rst_text = ''  # holds all text in all .rst files
for part in ['._tmp_copyright000', '._tmp_copyright001', '._tmp_copyright002']:
    shutil.copy('%s.rst' % part, source_dir)
    with open('%s.rst' % part, 'r') as rst_file:
        rst_text += rst_file.read()

# Copy figures and movies directories
figdirs = glob.glob('fig*') + glob.glob('mov*')
for figdir in figdirs:
    destdir = None
    if figdir.startswith('fig'):
        # Figures can be anywhere (copied by sphinx to _images)
        destdir = os.path.join(source_dir, figdir)
    elif figdir.startswith('mov'):
        # Movies must be in _static
        # Copy only the movies if they are needed through local filenames
        if '"'+ figdir in rst_text or '<' + figdir in rst_text:
            destdir = os.path.join(source_dir, '_static', figdir)
    if destdir is not None and os.path.isdir(figdir) and not os.path.isdir(destdir):
        msg = 'copy: %s to %s' % (figdir, destdir)
        print(msg)
        logging.info(msg)
        shutil.copytree(figdir, destdir)

# Copy needed figure files in current dir (not in fig* directories)
for rstfile in glob.glob(os.path.join(source_dir, '*.rst')) + glob.glob(os.path.join(source_dir, '.*.rst')):
    f = open(rstfile, 'r')
    text = text_orig = f.read()
    f.close()
    import regex as re
    figfiles = [name.strip() for name in
                re.findall('.. figure:: (.+)', text)]
    local_figfiles = [name for name in figfiles if not os.sep in name]

    for name in figfiles:
        basename = os.path.basename(name)
        if name.startswith('http') or name.startswith('ftp'):
            pass
        else:
            if not os.path.isfile(os.path.join(source_dir, basename)):
                msg = 'copy: %s to %s' % (name, source_dir)
                print(msg)
                logging.info(msg)
                shutil.copy(name, source_dir)
            if name not in local_figfiles:
                # name lies in another directory, make local reference to it
                # since it is copied to source_dir
                text = text.replace('.. figure:: %s' % name,
                                    '.. figure:: %s' % basename)
                logging.info('edit: figure path to %s' % basename)
    if text != text_orig:
        f = open(rstfile, 'w')
        f.write(text)
        f.close()

# Copy linked local files, placed in _static*, to source_dir/_static
staticdirs = glob.glob('_static*')
for staticdir in staticdirs:
    if os.listdir(staticdir):  # copy only if non-empty dir
        cmd = 'cp -r %(staticdir)s/* %(source_dir)s/_static/' % vars()
        logging.info('running %s' % cmd)
        system(cmd)

# Create custom files in _static/_templates?
if '**Show/Hide Code**' in rst_text:
    with open(os.path.join(sphinx_rootdir, '_templates', 'page.html'), 'w') as f:
        f.write("""
{% extends "!page.html" %}

{% set css_files = css_files + ["_static/custom.css"] %}

{% block footer %}
 <script type="text/javascript">
    $(document).ready(function() {
        $(".toggle > *").hide();
        $(".toggle .header").show();
        $(".toggle .header").click(function() {
            $(this).parent().children().not(".header").toggle(400);
            $(this).parent().children(".header").toggleClass("open");
        })
    });
</script>
{% endblock %}
""")
    with open(os.path.join(sphinx_rootdir, '_static', 'custom.css'), 'w') as f:
        f.write("""
.toggle .header {
    display: block;
    clear: both;
}

.toggle .header:after {
    content: " ▼";
}

.toggle .header.open:after {
    content: " ▲";
}
""")

os.chdir(sphinx_rootdir)
if '--runestone' not in sys.argv:
    # Compile web version of the sphinx document
    print(os.getcwd())
    logging.info('running make clean and make html')
    system('make clean')
    system('make html')

    print('Fix generated files:',)
    os.chdir('_build/html')
    for filename in glob.glob('*.html') + glob.glob('.*.html'):
        print(filename)
        f = open(filename, 'r'); text = f.read(); f.close()
        text_orig = text
        # Fix double title in <title> tags
        text = re.sub(r'<title>(.+?) &mdash;.+?</title>', r'<title>\g<1></title>', text)
        # Fix untranslated math (e.g. in figure captions and raw html)
        text = re.sub(r':math:`(.+?)`', r' \( \g<1> \) ', text)
        # Fix links to movies
        text = re.sub(r'''src=['"](mov.+?)['"]''', r'src="_static/\g<1>"', text)
        # Fix movie frames in javascript player
        text = text.replace(r'.src = "mov', '.src = "_static/mov')
        # Fix admonition style
        text = text.replace('</head>', '''
       <style type="text/css">\n         div.admonition {
           background-color: whiteSmoke;
           border: 1px solid #bababa;
         }
       </style>
      </head>
    ''')

        # Check if external links should pop up in separate windows
        if '.. NOTE: Open external links in new windows.' in text:
            text = text.replace('<a class="reference external"',
                                '<a class="reference external" target="_blank"')

        # Make a link for doconce citation in copyright
        if '. Made with DocOnce' in text:
            text = text.replace('. Made with DocOnce', '')
            text = text.replace('      Created using <a href="https://sphinx-doc.org/">Sphinx', '      Created using <a href="https://github.com/doconce/doconce">DocOnce</a> and <a href="https://sphinx-doc.org/">Sphinx')
        # Remove (1), (2), ... numberings in identical headings
        headings_wno = re.findall(r'(?<=(\d|"))>([^>]+?)          \((\d+)\)<', text)
        for dummy, heading, no in headings_wno:
            heading = heading.strip()
            text = re.sub(r'>%s +\(%d\)<' %
                          (re.escape(heading), int(no)),
                          '>%s<' % heading, text)
            text = re.sub(r'title="%s +\(%d\)"' %
                          (re.escape(heading), int(no)),
                          r'title="%s"' % heading, text)

        if os.path.isfile(filename + '.old~~'):
            os.remove(filename + '.old~~')
        f = open(filename, 'w'); f.write(text); f.close()
        if text != text_orig:
            logging.info('edit: %s' % filename)
    os.chdir('../../')
    print('\n\ngoogle-chrome tmp_sphinx-rootdir4/_build/html/index.html\n')

else:
    # Add directory for RunestoneInteractive book
    use_runestonebooks_style = True  # False: use user-chosen style
    print("""

create RunestoneInteractive directory
""")
    sys.path.insert(0, os.curdir)
    import conf as source_dir_conf  # read data from conf.py

    if not os.path.isdir('RunestoneTools'):
        system('git clone https://github.com/RunestoneInteractive/RunestoneComponents.git')
    os.chdir('RunestoneComponents')
    logging.info('creating RunestoneInteractive directory')

    # Edit conf.py
    # This one does not work anymore: run runestone init instead,
    print('RunestoneInteractive has recently changed its setup - must abort')
    sys.exit(1)
    # it's the file runestone/__main__.py and function init()
    # Need to build a bash script that runs the command and feeds the answers
    # See also https://github.com/RunestoneInteractive/RunestoneComponents
    f = open('conf.py.prototype', 'r');  text = f.read();  f.close()
    text = text.replace('<ENTER YOUR PROJECT NAME HERE>', source_dir_conf.project)
    text = text.replace('<INSERT YOUR PROJECT NAME HERE>', source_dir_conf.project)
    text = text.replace('<ENTER YOUR COPYRIGHT NOTICE HERE>', source_dir_conf.copyright)
    text = text.replace('<INSERT YOUR PROJECT NAME OR OTHER TITLE HERE>', source_dir_conf.project)
    text = text.replace('<INSERT YOUR PROJECT NAME OR OTHER SHORT TITLE HERE>', source_dir_conf.project)
    text = text.replace('html_theme_path = ["_templates"]', 'html_theme_path = ["_templates", "../_themes"]')
    if not use_runestonebooks_style:
        text = text.replace("html_theme = 'sphinx_bootstrap'", "html_theme = '%s'" % source_dir_conf.html_theme)
        text = re.sub(r'html_theme_options = \{.+?\}', 'html_theme_options = ' + str(source_dir_conf.html_theme_options) if hasattr(source_dir_conf, 'html_theme_options') else 'html_theme_options = {}', text, flags=re.DOTALL)
    f = open('conf.py', 'w');  f.write(text);  f.close()

    # Copy .rst files from sphinx dir
    rst_files = [os.path.join(os.pardir, 'index.rst')] + glob.glob(os.path.join(os.pardir, '*.rst')) + glob.glob(os.path.join(os.pardir, '._*.rst'))
    for filename in rst_files:
        print('copying', filename, 'to _sources')
        logging.info('copy: %s to _sources' % filename)
        shutil.copy(filename, '_sources')
    print('*** running paver build to build the RunestoneInteractive book')
    logging.info('running paver build to create the RunestoneInteractive book')
    system('paver build')

    print('\n\ngoogle-chrome tmp_sphinx-rootdir4/RunestoneTools/build/index.html')
