#!/usr/bin/python3
import os
import re
import time
import json
import urllib.request
import sys
from pymongo import MongoClient
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
from enum import Enum


class Crawler:
    driver = webdriver.Chrome()
    momo_url = 'https://www.momoshop.com.tw'
    pattern = "[-`~!@#$^&*()=|{}':;',\\[\\].<>/?~！@#￥……&*（）&;|{}【】‘；：”“'。，、？+ ]"
    image = Image.new('RGB', (1, 1), (255, 255, 255))
    vendor_max_page = 0
    # MonGo DB
    client = MongoClient()
    db = client.surpass
    write_db_list = []

    def __init__(self, result_directory, dbtype):
        # result_directory = 'result'
        self.result_directory = result_directory
        self.vendor_directory = result_directory + '/vendor'
        self.create_directory(result_directory)
        self.create_directory(self.vendor_directory)
        self.vendors = self.load_vendors()
        self.table_vendor = self.db.vendor
        if dbtype == DbType.MONGO.value:
            self.write_db_list.append(DbType.MONGO.value)

    def start(self):
        for vendor in self.vendors:
            self.crawler_vendor(vendor)
        self.driver.quit()

    @staticmethod
    def create_directory(path):
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
        try:
            self.next_page(vendor, 1)
        except WebDriverException:
            print('『' + vendor + '』找不到下一頁的按鈕。')

    def next_page(self, vendor, page):

        if page > 1 and page > self.vendor_max_page:
            print(vendor + '沒有下一頁了')
            return

        self.driver.get(
            'https://www.momoshop.com.tw/search/searchShop.jsp?keyword=' + vendor + '&curPage=' + str(page))
        time.sleep(2.5)

        if page == 1:
            elements = self.driver.find_elements_by_xpath(
                "//div[@class='pageArea']/ul/li/a")
            self.vendor_max_page = int(elements[-1].get_attribute('pageidx'))
            print("﹝%s﹞總共有 %d 頁" % (vendor, self.vendor_max_page))

        print('=====' + vendor + '==========開始爬第' + str(page) + '頁==========')

        directory = self.vendor_directory + '/' + vendor

        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        list_area = soup.find('div', {'class': 'listArea'}).find('ul')
        for item_li in list_area.select('li'):
            item = item_li.select_one('a.goodsUrl')
            # 產品編號
            the_id = item_li['gcode']
            # 產品網址
            # url = momo_url + item['href']
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
            except (urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError, ValueError):
                try:
                    urllib.request.urlretrieve(little_image_url, filepath)
                    print(filename, little_image_url)
                except (
                        urllib.request.HTTPError, urllib.request.URLError, urllib.request.ContentTooShortError,
                        ValueError):
                    self.image.save(filepath, "PNG")
                    print(filename, 'empty image')

            # save db
            self.writeDb(self.table_vendor, vendor, the_id, name)

        self.next_page(vendor, page + 1)

    def writeDb(self, table, vendor, img_id, ch_name):
        for db_name in self.write_db_list:
            if db_name == DbType.MONGO.value:
                table.insert_one({
                    "vendor": vendor,
                    "img_id": img_id,
                    "ch_name": ch_name,
                })
        

class Instruction(Enum):
    DBTYPE = "-d"


class DbType(Enum):
    MONGO = "mongo"


def main():
    dbtype = ""
    if len(sys.argv) > 1 and type(sys.argv[1] is str):
        argu = sys.argv[1]
        argus = re.split(" ", argu)
        if argus[0] == Instruction.DBTYPE.value:
            dbtype = argus[1]
    crawler = Crawler('result', dbtype)
    crawler.start()


if __name__ == "__main__":
    main()
