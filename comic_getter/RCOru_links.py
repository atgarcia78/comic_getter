import json
import re
import operator
import time
import os
from requests_html import HTMLSession
import argparse


parser = argparse.ArgumentParser(description="comics")
parser.add_argument("url", help="url")
args = parser.parse_args()
main_link = args.url    


[base_link, comicname] = main_link.split['/']
dl_link = base_link + "/uploads/manga/" + comicname + "/chapters/"

    
session = HTMLSession()

try:

    i = 1
    while True:

        r = session.request("GET", main_link + "/i")
        if r.status_code == 200:
            j = 1
            while True:
                if j < 10:
                    page = "0" + str(j)
                else:
                    page = str(j)
                link = dl_link + str(i) + "/" + page + ".jpg"
                print(link)
                r1 = session.request("HEAD", link)
                if r1.status_code == 200:
                    page = requests.get(link, stream=True)
                    with open("/Users/antoniotorres/testing/xmen-2019/" +i+"/" + page + ".jpg", 'wb') as file:
                        file.write(page.content)       
                else:
                   break
        else:
            break
                    

               