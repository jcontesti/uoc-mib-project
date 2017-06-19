from kafka import KafkaProducer
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream
import settings
import os

CONSUMER_KEY = os.environ.get('CONSUMER_KEY')
CONSUMER_SECRET = os.environ.get('CONSUMER_SECRET')
ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
ACCESS_TOKEN_SECRET = os.environ.get('ACCESS_TOKEN_SECRET')

class KafkaListener(StreamListener):

    def __init__(self):
        super(KafkaListener, self).__init__()
        self.kafka_producer = KafkaProducer(bootstrap_servers='localhost:9092', value_serializer=lambda v: v.encode('utf-8'))
        
    def on_data(self, data):
        self.kafka_producer.send('twitter-data', data)
        return True

    def on_error(self, status):
        print(status)
        return True

if __name__ == '__main__':
    kafka_listener = KafkaListener()
    auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    
    stream = Stream(auth, kafka_listener)
    stream.filter(locations=[
        -85.9351,8.2876,-82.6392,11.2323,  # Costa Rica
        -73.56,-55.19,-53.64,-21.78,       # Argentina
        -6.5,36.28,3.3,43.68,              # Spain
        -81.156,-5.0159,-75.1925,1.8822,   # Ecuador 
        -70.05,-22.98,-57.19,-9.47,        # Bolivia
        -62.64,-27.61,-54.26,-19.29,       # Paraguay
        -73.35,0.65,-59.54,15.92,          # Venezuela
        -88.9124,12.9939,-83.1555,16.2252  # Honduras
    ])
                             
