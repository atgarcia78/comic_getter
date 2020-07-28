import json
import re
import operator
import time
import os
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from pathlib import Path
from tqdm import tqdm



#Pending make skipable issues and consider allowing hq download.
class RCO_Comic:
    '''Collection of functions that allow to download a 
    readcomiconline.to comic with all it's issues.'''

    def __init__(self, main_link):
        '''Initializes main_link attribute. '''

        # Seed link that contains all the links of the different issues.
        self.main_link = main_link

        # Extract data from config.json
        dir_path = Path(f"{os.path.dirname(os.path.abspath(__file__))}/config.json")
        with open(dir_path) as config:
            data = json.load(config)
        self.driver_path = data["chromedriver_path"]
        self.download_directory_path = data["download_dir"]
        options = Options()
        options.page_load_strategy = 'eager'
        #options.headless=True
        #options.add_extension("/Users/antoniotorres/Downloads/extension_1_1_0_0.crx")
        #options.add_extension("/Users/antoniotorres/Downloads/extension_1_27_10_0.crx")
        self.driver = webdriver.Chrome(executable_path=self.driver_path,chrome_options=options)
        self.driver.set_window_size(1,1)
        self.main_window = None
 
    def get_comic_and_issue_name(self, issue_link):
        '''Finds out comic and issue name from link.'''
        
        # Re module is used to get issue and comic name.
        generic_comic_name = re.compile(r"(?<=comic/)(.+?)/(.+?)(?=\?)", re.I)
        name_and_issue = re.search(generic_comic_name, issue_link)

        # comic_issue_names[0] is the comic's link name, comic_issue_names[1] is
        # the comic name and comic_issue_names[2] is the issues name.
        comic_issue_name = [name_and_issue[1], name_and_issue[2], issue_link]
        return comic_issue_name

    def is_comic_downloaded(self, comic_issue_name):
        '''Checks if comic has already been downloaded.'''

        download_path = Path(f"{self.download_directory_path}/{comic_issue_name[1]}/{comic_issue_name[2]}")
        if os.path.exists(download_path):
            print(f"{comic_issue_name[2]} has already been downloaded.")
            return True
        else:
            return False  

    def get_issues_links(self):
        '''Gather all individual issues links from main link.'''

        self.driver.get(self.main_link)
        # A 60 second margin is given for rowser to bypass cloudflare.
        try:
            wait = WebDriverWait(self.driver, 60)
            # element = wait.until(ec.presence_of_element_located(
            #    (By.CLASS_NAME, "listing")))
            # # The whole html code is downloaded.
            element = wait.until(ec.visibility_of_element_located(
                (By.LINK_TEXT, "ReadComicOnline.to")))
            body = self.driver.find_element_by_tag_name("body")
            body = str(body.get_attribute('innerHTML'))
            
            # table = self.driver.find_element_by_class_name("listing")
            # self.main_window = self.driver.current_window_handle
            # body = table.get_attribute('innerHTML')
            # self.driver.quit()
            # Re module is used to extract relevant links.
            core_link = "https://readcomiconline.to"
            generic_link = re.compile(r'(?<=")/Comic/.+?id=\d+(?=")', re.I)
            target_links = re.findall(generic_link, body)
            issues_links = []
            for link in target_links:
                #full_link = core_link + link
                full_link = core_link + link + "&quality=hq&readType=1"
                issues_links.append(full_link)
            return (issues_links)

            
        except Exception as e:
            print(e)
            return
        
    
    
    def get_pages_links(self, i, issue_link):
        ''' Gather the links of each page of an issue.'''

        info = []
        info = self.get_comic_and_issue_name(issue_link)
        comic_name = info[0]
        comic_issue = info[1]
        

        main_window = self.driver.current_window_handle
        windows = self.driver.window_handles
        n_windows = len(self.driver.window_handles)

        self.driver.execute_script('window.open();')
        while len(self.driver.window_handles) == n_windows:
            time.sleep(0.5)
         
        windows = self.driver.window_handles
        
        for guid in windows:
            if guid != main_window:
                self.driver.switch_to_window(guid)
                break;

        new_window = self.driver.current_window_handle
        issue_data = []
        try:
            self.driver.get(issue_link)
            wait = WebDriverWait(self.driver, 3600)
            #wait until the javascript with the images information is downloaded. And use the links
            #in the javascript itself, so there's no need to wait to download every image 
            elements = []
            elements = wait.until(ec.presence_of_all_elements_located( (By.TAG_NAME,"script") ))
            for i, tag in enumerate(elements):
                html_page = tag.get_attribute('innerHTML')
                if "lstImages" in html_page:
                    break 

            generic_page_link = re.compile(
                r'(?<=")https://2\.bp\.blogspot\.com/.+?(?=")', re.I)
            pages_links = re.findall(generic_page_link, html_page)
            issue_data = [comic_name, comic_issue, pages_links] 

            self.driver.switch_to_window(main_window)
            self.driver.close()
            self.driver.switch_to_window(new_window)
        
        except Exception as e:
            print(e)
            self.driver.switch_to_window(main_window)
            self.driver.close()
            self.driver.switch_to_window(new_window)
            return
            

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


