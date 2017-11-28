"""
WSGI config for cell_again project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os, sys, site
script_directory = os.getcwd()
VIRTUALENV_DIR = '/home/WWW/.virtualenvs/cellagain.com/'

# Add the site-packages of the chosen virtualenv to work with
site.addsitedir(os.path.join(VIRTUALENV_DIR, 'local/lib/python2.7/site-packages'))

# always 2 folders away, /static/scripts or /public/scripts
# script should be located at something like: '/home/WWW/production/public/scripts/'
# we're appending the project path to the python sys path
# this should be something like: sys.path.append('/home/WWW/production/private')
path_to_append = os.path.join(script_directory, '..', '..', 'private')
sys.path.append(path_to_append)

# pointing deployment wsgi to the production settings by default
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cell_again.settings")

# Activate your virtual env
activate_env=os.path.expanduser(os.path.join(VIRTUALENV_DIR, "bin/activate_this.py"))
execfile(activate_env, dict(__file__=activate_env))

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
