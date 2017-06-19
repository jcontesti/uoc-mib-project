#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pyspark import SparkContext, SparkConf
from pyspark.streaming import StreamingContext
from pyspark.streaming.kafka import KafkaUtils
from nltk.corpus import stopwords 
from nltk import word_tokenize
from string import punctuation
from pyspark.sql import SparkSession
import json
import ast
import nltk 
import csv
import unicodedata
import pandas as pd

SENTIMENT_VERSION = 1.0

corpus_positive_words = set([])
corpus_negative_words = set([])

spark_session = None

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')

def load_corpus():
    
    global corpus_positive_words, corpus_negative_words
    
    with open('ElhPolar_esV1.lex','r') as f:
        reader = csv.reader(f, delimiter='\t')
        for word, sentiment in reader:
            word = strip_accents(word.replace('_', ' '))
            if sentiment == 'positive':
                corpus_positive_words.add(word)
            if sentiment == 'negative':
                corpus_negative_words.add(word)

    corpus_positive_words = list(corpus_positive_words)
    corpus_negative_words = list(corpus_negative_words)
                
def process_message(message):
    message_items = message.collect()
    for tweet in message_items:
        process_tweet(json.loads(tweet[1]))

def process_tweet(tweet):
    
    # Ignore tweets from users that can be spammers
    followers_count = int(tweet.get('user').get('followers_count'))
    friends_count = int(tweet.get('user').get('friends_count'))
    if followers_count > 0 and friends_count > 0 and followers_count/friends_count < 0.25:
        return
    
    # Ignore retweets
    if tweet.get('retweeted_status'):
        return
    
    # Ignore tweets not in Spanish
    if tweet.get('lang') != 'es':
        return
    
    # Ignore tweets not from allowed countries
    allowed_country_codes = ['CR', 'AR', 'ES', 'EC', 'BO', 'PY', 'VE', 'HN']
    if tweet.get('place') == None or tweet.get('place').get('country_code') not in allowed_country_codes:
        return
    
    tweet_id = tweet.get('id')
    user_id = tweet.get('user').get('id')
    text = tweet.get('text')
    country_code = tweet.get('place').get('country_code')
    lang = tweet.get('lang')
    created_at = tweet.get('created_at')
    sentiment = analyse_sentiment(text)
    
    record = {'id': tweet_id, 
              'user_id': user_id, 
              'text': text, 
              'country_code': country_code,
              'lang': lang,
              'created_at': created_at,
              'sentiment': sentiment,
              'sentiment_version': SENTIMENT_VERSION}
    
    df = pd.DataFrame(record, index=[0])
    
    tweet_to_mongodb = spark_session.createDataFrame(df)
    tweet_to_mongodb.write.format("com.mongodb.spark.sql.DefaultSource").mode("append").save()
    
def analyse_sentiment(text):
    
    global corpus_positive_words, corpus_negative_words
    
    stopwords_spanish = stopwords.words('spanish')

    punctuation_spanish = list(punctuation)  
    punctuation_spanish.extend(['¿', '¡'])  
    
    cleaned_text = [strip_accents(word) for word in word_tokenize(text.lower()) 
                    if word not in stopwords_spanish and word not in punctuation_spanish]
    
    positive_sentiment = sum(corpus_positive_words.count(word) for word in cleaned_text)
    negative_sentiment = sum(corpus_negative_words.count(word) for word in cleaned_text)
    
    return positive_sentiment - negative_sentiment

conf = SparkConf().setAppName('twitter-analysis-app')
sc = SparkContext(conf=conf)
sc.setLogLevel("ERROR")

stc = StreamingContext(sc, 60)

spark_session = SparkSession.builder.appName('twitter-analysis-app')\
    .config('spark.mongodb.output.uri', 'mongodb://127.0.0.1:27017')\
    .config('spark.mongodb.output.database', 'twitter_data')\
    .config('spark.mongodb.output.collection', 'twitter_data')\
    .getOrCreate()

kafka_stream = KafkaUtils.createStream(
    stc, 
    zkQuorum='localhost:2181', 
    groupId='group-id-spark-consumer', 
    topics={'twitter-data': 1},
    kafkaParams={
        'auto.offset.reset': 'smallest',
        'auto.commit.enable': 'true'})

load_corpus()

kafka_stream.foreachRDD(process_message)

stc.start()
stc.awaitTermination()
