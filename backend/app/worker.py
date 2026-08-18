from redis import Redis
from rq import Worker
from .config import settings

if __name__ == "__main__":
    Worker(["gpx"], connection=Redis.from_url(settings.redis_url)).work()
