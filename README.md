# true_nth_usa_portal_demo
Demo for the Movember True NTH USA portal - early summer 2015

## INSTALLATION

Pull down prerequisite packages

```bash
$ sudo apt-get install python-virtualenv
```

From the parent directory where you wish to install the portal, pull
down the code and create a virtual environment to isolate the 
requirements from the system python

```bash
$ git clone https://github.com/uwcirg/true_nth_usa_portal_demo.git portal
$ virtualenv portal
$ cd portal
```

Activate the virtual environment, patch setuptools, and install the
project requirements (into the virtual environment)

```bash
$ source bin/activate
$ pip install -U setuptools
$ pip install -r requirements.txt
```

## CONFIGURE

Copy the default to the named configuration file

```bash
$ cp application.cfg.default application.cfg
```

Obtain `consumer_key` and `consumer_secret` values from https://developers.facebook.com/apps (write values to `application.cfg`)

## RUN
```bash
$ python client.py
```
