# -*- coding: utf-8 -*-
# !/usr/bin/python3
import os
import re
import time
import json
import urllib.request
import sys
import logging
import subprocess
import shlex
from pymongo import MongoClient
import pymongo.errors
from PIL import Image
from selenium import webdriver
from bs4 import BeautifulSoup
from enum import Enum
import argparse


class Crawler:

    class MongoDB():

        def __init__(self, dbpath):
            print('使用MongoDB儲存資料')
            self.mongod = subprocess.Popen(
                shlex.split(
                    "mongod --dbpath {0}".format(os.path.expanduser(dbpath)))
            )
            self.client = MongoClient()
            self.db_mongo = self.client.surpass
            self.table_vendor = self.db_mongo.vendor

        def get_vendor_table(self):
            return self.table_vendor

        def write(self, vendor, img_id, ch_name):
            try:
                self.table_vendor.insert_one({
                    "vendor": vendor,
                    "img_id": img_id,
                    "ch_name": ch_name,
                })
            except pymongo.errors.ServerSelectionTimeoutError as err:
                logging.error(err)

        def terminate(self):
            self.mongod.terminate()

    def __init__(self, result_directory, dbtype, dbpath):
        self.result_directory = result_directory
        self.vendor_directory = result_directory + '/vendor'
        self.vendors = self.load_vendors()
        self.momo_host = 'https://www.momoshop.com.tw'
        self.pattern = "[-`~!@#$^&*()=|{}':;',\\[\\].<>/?~！@#￥……&*（）&;|{}【】‘；：”“'。，、？+ ]"
        self.image = Image.new('RGB', (1, 1), (255, 255, 255))
        self.init_logger()
        self.init_directories
        self.init_database(dbtype, dbpath)

    def init_database(self, dbtype, dbpath):
        self.dbtype_objects = {'mongo': self.MongoDB}
        if dbtype is not None and dbpath is not None:    
            self.db = self.dbtype_objects[dbtype](dbpath)

    def init_logger(self):
        log_filename = "{}/{}.txt".format(self.result_directory, time.time())
        logging.basicConfig(filename=log_filename, level=logging.DEBUG)
        global logger
        logger = logging.getLogger(__name__)

    def init_directories(self):
        self.create_directory(self.result_directory)
        self.create_directory(self.vendor_directory)

    def start(self):
        self.driver = webdriver.Chrome()
        self.delay_second = 5
        self.vendor_max_page = 0
        for vendor in self.vendors:
            self.crawler_vendor(vendor)
        self.driver.quit()
        self.db.terminate()

    def create_directory(self, path):
        if not os.path.exists(path):
            os.makedirs(path)

    @staticmethod
    def get_number(text):
        arr = re.findall('[0-9]+', text)
        str = ''
        for char in arr:
            str += char
        if len(str) > 0:
            return int(str)
        return 0

    @staticmethod
    def load_vendors():
        with open('catchimg3.json', encoding='utf8') as data_file:
            data = json.load(data_file)
        bigkey = data['bigkey']

        arr = []
        for vendor in bigkey:
            arr.append(vendor['keyword'])
        return arr

    def crawler_vendor(self, vendor):
        self.create_directory(self.vendor_directory + '/' + vendor)
        self.trigger_click_page(vendor)

    def trigger_click_page(self, vendor):
        self.next_page(vendor, 1)

    def get_vendor_max_page(self, vendor, page):
        elements = self.driver.find_elements_by_xpath(
            "//div[@class='pageArea']/ul/li/a")
        try:
            self.vendor_max_page = int(elements[-1].get_attribute('pageidx'))
        except IndexError as err:
            logging.error(err)
            print("「{}」找不到頁數標籤，準備重整頁面並等待10秒...".format(vendor))
            self.driver.refresh()
            time.sleep(10)
            self.get_vendor_max_page(vendor, page)

    def next_page(self, vendor, page):
        if page > 1 and page > self.vendor_max_page:
            print(vendor + '沒有下一頁了')
            return

        self.driver.get(
            'https://www.momoshop.com.tw/search/searchShop.jsp?keyword=' + vendor + '&curPage=' + str(page))
        time.sleep(self.delay_second)

        if page == 1:
            self.get_vendor_max_page(vendor, page)
            print("﹝%s﹞總共有 %d 頁" % (vendor, self.vendor_max_page))

        print('=====' + vendor + '==========開始爬第' + str(page) + '頁==========')

        directory = self.vendor_directory + '/' + vendor

        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        except TypeError as err:
            logger.error(err)
            return
        list_area = soup.find('div', {'class': 'listArea'}).find('ul')
        for item_li in list_area.select('li'):
            item = item_li.select_one('a.goodsUrl')
            # 產品編號
            the_id = item_li['gcode']
            # 產品網址
            url = self.momo_host + item['href']
            # 產品大圖網址，置換小的圖片網址為大的
            little_image_url = item.find('img')['src']
            image_url = little_image_url.replace('L.jpg', 'B.jpg')
            # 產品名稱
            name = item.find('p', {'class': 'prdName'}).text
            # 產品Slogan
            # slogan = item.find('p', {'class': 'sloganTitle'}).text
            # 產品價格
            money_text = item.find('p', {'class': 'money'}).text
            # money = get_number(money_text)
            # print(url, image_url, name, slogan, money)

            filename = vendor + '_' + \
                re.sub(self.pattern, "", name) + '_' + the_id + '.jpg'
            filepath = directory + '/' + filename
            try:
                urllib.request.urlretrieve(image_url, filepath)
                print(filename, image_url)
            except (
                    urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError,
                    ValueError) as err:
                try:
                    logging.error(err)
                    urllib.request.urlretrieve(little_image_url, filepath)
                    print(filename, little_image_url)
                except (
                        urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError,
                        ValueError) as err:
                    logging.error(err)
                    self.image.save(filepath, "PNG")
                    print(filename, 'empty image')

            # save db
            self.db.write(vendor, the_id, name)

        self.next_page(vendor, page + 1)


def main():
    parser = argparse.ArgumentParser(
        prog="MomoProductCrawler",
    )
    parser.add_argument(
        "-r", metavar="result_directory", dest="result_directory",
        help="choice a directory to save momo images.",
    )
    parser.add_argument(
        "-d", metavar="database", dest="database",
        help="choice a database which you needs.",
    )
    parser.add_argument(
        "-dbpath", metavar="database_path", dest="database_path",
        help="choice a database dbpath where you save."
    )
    args = parser.parse_args()
    result_directory = args.result_directory
    dbtype = args.database
    dbpath = args.database_path
    crawler = Crawler(result_directory, dbtype, dbpath)
    crawler.start()


if __name__ == "__main__":
    main()
