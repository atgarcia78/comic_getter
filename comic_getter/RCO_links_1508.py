import json
import re
import operator
import time
import os
from requests_html import HTMLSession
import sys
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as ec

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from pathlib import Path
from tqdm import tqdm
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem



#Pending make skipable issues and consider allowing hq download.
class RCO_Comic:
    '''Collection of functions that allow to download a 
    readcomiconline.to comic with all it's issues.'''

    def __init__(self, main_link):
        '''Initializes main_link attribute. '''

        software_names = [SoftwareName.CHROME.value]
        operating_systems = [OperatingSystem.MACOS.value]   

        user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_systems, limit=100)

        # Get list of user agents.
        user_agents = user_agent_rotator.get_user_agents()

        # Get Random User Agent String.
        user_agent = user_agent_rotator.get_random_user_agent()
        
        # Seed link that contains all the links of the different issues.
        self.main_link = main_link
        self.issue_pages = []
        self.session = HTMLSession()
        # Extract data from config.json
        dir_path = Path(f"{os.path.dirname(os.path.abspath(__file__))}/config.json")
        with open(dir_path) as config:
            data = json.load(config)
        self.driver_path = data["chromedriver_path"]
        self.download_directory_path = data["download_dir"]
        options = Options()
        #options.page_load_strategy = 'eager'
        options.headless = True
        options.add_argument("user-agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36'")
        #options.add_argument("user-agent=" + user_agent)
        #options.add_extension("/Users/antoniotorres/Downloads/extension_1_1_0_0.crx")
        #options.add_extension("/Users/antoniotorres/Downloads/extension_1_27_10_0.crx")
        self.driver = webdriver.Chrome(executable_path=self.driver_path,options=options)
        #self.driver.set_window_size(1,1)
        self.driver.implicitly_wait(15) # seconds
        self.main_window = None
        
        i = 0

        #We use Selenium at first approach to pass the cloudfare
        while i < 5:
            try:
                print("Trying to bypass cloudfare...")
                self.driver.get(self.main_link)
                wait = WebDriverWait(self.driver, 30)
                wait.until(ec.title_contains("comic"))
                assert "comic" in self.driver.title
                break
            except Exception as e:
                i += 1
        print(self.driver.title)
        if not "comic" in self.driver.title:
            raise Exception("Try again")

        self.init_session()
        
    def init_session(self):
        
        self.session.headers = self.driver.requests[0].headers
        print(self.session.headers)
        cookies = self.driver.get_cookies()
        for cookie in cookies:
            #print(cookie)
            self.session.cookies.set(cookie['name'], cookie['value'])
   
    def get_comic_and_issue_name(self, issue_link):
        '''Finds out comic and issue name from link.'''
        
        # Re module is used to get issue and comic name.
        
        generic_comic_name = re.compile(r"(?<=Comic/)(.+?)/(.+?)(?=\?)", re.I)
        name_and_issue = re.search(generic_comic_name, issue_link)
        
        # comic_issue_names[0] is the comic's link name, comic_issue_names[1] is
        # the comic name and comic_issue_names[2] is the issues name.
        comic_issue_name = [name_and_issue[1], name_and_issue[2], issue_link]
        return comic_issue_name


    def get_issues_links(self):
        '''Gather all individual issues links from main link.'''

 
        try:
           
            

            body = WebDriverWait(self.driver, 120).until(ec.presence_of_element_located(
                (By.CLASS_NAME, "listing"))).get_attribute('innerHTML')
           
            
            core_link = "https://readcomiconline.to"
            generic_link = re.compile(r'(?<=")/Comic/.+?id=\d+(?=")', re.I)
            target_links = re.findall(generic_link, body)
            issues_links = []
            for link in target_links:
                full_link = core_link + link + "&quality=hq&readType=1"
                issues_links.append(full_link)
            return (issues_links)

            
        except Exception as e:
            print(e)
            return
        
    
        
    
    def get_pages_links(self, issue_link):
        ''' Gather the links of each page of an issue.'''

        #print(issue_link)
        info = []
        info = self.get_comic_and_issue_name(issue_link)
        comic_name = info[0]
        comic_issue = info[1]
        
        

        issue_data = []
        pages_links = []

        try:
            time.sleep(5)
            print("Scraping: " + issue_link)
            
            r = self.session.request("GET", issue_link, timeout=30)
            print(r.text)
            input()"mira"
            print(self.session.cookies)
            r.html.render()
            print(self.session.cookies)
            self.session.cookies = cookies
            input("mira")
            #print(issue_link)
            #print(r.status_code)
            html_page = r.text
            print(r.text.lower())
            if "<title>Just a moment...</title>" in html_page:
                print("CLOUDFARE")
                return(sys.exit("CLOUDFARE"))
                
            if ("are you human" or "areyouhuman") in r.text.lower(): 
                print("CAPTCHA")
                self.driver.get(issue_link)
                input("mira")
                r = self.session.request("GET", issue_link, timeout=30)
                html_page = r.text

            #print(html_page[0:300])
                     
            generic_page_link = re.compile(
                r'(?<=")https://2\.bp\.blogspot\.com/.+?(?=")', re.I)
            pages_links = re.findall(generic_page_link, html_page)
            issue_data = [comic_name, comic_issue, pages_links] 
        
        except Exception as e:
            print(e)
  
            
        self.issue_pages.append(issue_data)    

        return issue_data
        
    def download_issue(self, issue_data):
        ''' Download image from link.'''

        download_path = Path(f"{self.download_directory_path}/"
                             f"{issue_data[0]}/{issue_data[1]}")

        download_path.mkdir(parents=True, exist_ok=True)
        #print(f"Started downloading {issue_data[2]}")

        # Create progress bar that monitors page download.
        with tqdm(total=len(issue_data[2])) as pbar:
            for index, link in enumerate(issue_data[2]):

                page_path = Path(f"{download_path}/page{index}.jpg")
                if page_path.exists():
                    continue
                else:
                    page = requests.get(link, stream=True)
                    with open(page_path, 'wb') as file:
                        file.write(page.content)
                    pbar.update(1)


    def __del__(self):
        try:
            self.driver.quit()
        except Exception as e:
            print(e)