# Setup.

## Pull changes.
git pull origin master


## Settings file changes.
```
cp private/cell_again/settings-dev.py private/cell_again/settings.py
```

* Add doamin in ```ALLOWED_HOSTS``` list.
* [edit](https://gist.github.com/mattseymour/9205591) ```SECRET_KEY```.
* Change ```DATABASES``` variable.
* Add ```EMAIL_HOST```, ```EMAIL_HOST_USER``` and ```EMAIL_HOST_PASSWORD```.


## Update static files.

```
python manage.py collectstatic
```


## Copy .wsgi file.

```
cp public/scripts/django-sample.wsgi public/scripts/django.wsgi
```

Edit virtualenv path in this file if needed. Defaults to ```/home/WWW/.virtualenvs/cellagain.com```.


## Install pip packages.

```
pip install -r requirements.txt
```


## Update database tables.

```
python manage.py migrate
python manage.py createsuperuser
python manage.py oscar_populate_countries
```

## Add Categories, Product types, Products and Manage Orders from Dashboard.

/en/dashboard/
