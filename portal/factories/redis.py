import redis

def create_redis(url):
    return redis.Redis.from_url(url)
