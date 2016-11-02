Sessions
********

User session data is stored on the server via `Flask-Session 
<https://pythonhosted.org/Flask-Session/>`_, specifically in the same
`redis server <http://redis.io>`_ used to house the celery tasks.

redis-cli
=========

To view sessions (or other key/values) stored in redis, fire up the command
line interface (CLI) and execute simple queries::

    $ redis-cli
    127.0.0.1:6379> keys session*
    1) "session:0e17f42c-72d9-49c1-8066-195a1e770ad2"
    2) "session:42c94702-f1cb-447d-a998-409dbd5a99b6"
    3) "session:e116b0f1-2271-4473-97d0-6d910a4ff582"
    4) "session:2483797a-4261-4c6e-a3d0-1d19d6db6446"
    5) "session:3ae29547-943c-48e9-bc7e-b44b78c99551"
    6) "session:2264efc6-eb5a-46c0-98c6-fb458b435256"
    7) "session:1ac11b4b-bafc-41b5-9d93-b6fb90608054"
    [...]
    127.0.0.1:6379> ttl session:1ac11b4b-bafc-41b5-9d93-b6fb90608054
    (integer) 2677441
    127.0.0.1:6379> dump session:3e3ff4ed-2848-41e5-b78f-3ea909219d52
    "\x00\xc3@\xd4@\xdf\x16(dp1\nS'_fresh'\np2\nI01\ns \x11\x01id \x0e\x003 \x1b\x1f892f7fec2c15835660cba1324da22125\x17e167e65bbe5de394d486a744 0\x1007be014719895f627 E\x1f58b1ab0de00d8e2b5bc9bb4e29a7e3c7\x108329d9d2051ec0e84 \x86\x004@\x91\x03user\x80\x95\x035\nV2@\x11`\xa2\x006\xa0\x0c\t_permanent 0\x007`\xc6\x01s.\x06\x00\xb2\xbd\xb0W\xf3d\x18\x0c"

*ttl*: Time To Live.  Once expired, redis will delete the respective session.

*dump*: The session data is a pickled python dictionary.


    
