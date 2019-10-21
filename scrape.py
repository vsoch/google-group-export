from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from datetime import datetime

import argparse
import json
import os
import requests


class GoogleGroupsScraper(object):
    '''A class to scrape a google group. and output topics as raw text under
       exports/<org>/<group>/<date>/topics and raw urls for topics under
       exports/<org>/<group>/<date>/urls.txt
    '''

    def __init__(self, organization,
                       group_name, 
                       verbose=True):
        '''perform a scrape based on an organization, group name, and the class
           of the top div of the post list. You'll need to find this by viewing the source of
           the page and then finding the top div.
        '''

        self.url = 'https://groups.google.com/%s/forum/#!forum/%s' %(organization, group_name)
        self.org = organization
        self.group = group_name
        self.driver = self._get_driver()
        self.wait = WebDriverWait(self.driver, 30)
        self.verbose = verbose

        # Set up output folder, organized by <org>/<group>/<date>
        self.setup_output()
        self.topics_urls = []


    def setup_output(self):
        '''create an output folder based on the org, group, and date.
        '''
        now = datetime.now()
        datestr = "%s-%s-%s" %(now.year, now.month, now.day)
        org = self.org.replace('/', '-')
        group = self.group.replace('/', '-')
        output_path = os.path.join(get_here(), 'exports', org, group, datestr)

        # Only create if doesn't exist
        if os.path.exists(output_path):
            print("%s already exists, will only get new topics." % output_path)

        # Yeah, os.makedirs not great to use...
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        self.output_dir = output_path

        # Create folder for topics to save
        self.export_dir = os.path.join(self.output_dir, 'topics')
        if not os.path.exists(self.export_dir):
            os.mkdir(self.export_dir)

        print("Output: %s" % output_path)

    def save_all_posts(self):
        '''Save all the posts to a directory on the filesystem'''

        self.driver.get(self.url)

        # Tell the user to scroll to the bottom of the page
        self.scroll_to_bottom()
        self.get_topics_urls()

        # Iterate through topics
        for i, topic_url in enumerate(self.topics_urls):

            # Get raw urls for each post
            for raw_url in self.get_thread_urls(topic_url):
                self._save_content_of_message(raw_url)

    #### GoogleGroupsScraper interface ########################################

    def get_topics_urls(self):
        '''Return all the raw urls in the forum. Each is technically called a 
           topic, and links to a page with several posts for it. We save
           the urls to the output folder, in the case that some future
           person wants to implement a function to use it.
        '''
        # Retrieve urls that match topic pattern
        links = self.driver.execute_script("return document.querySelectorAll('a');")  
        url_format = 'https://groups.google.com/%s/forum/#!topic' % self.org

        # Find links based on the format
        links = [link.get_attribute('href') for link in links if link.get_attribute('href')] 
        self.topics_urls = [link for link in links if link.startswith(url_format)] 
        
        if self.verbose:
            print("Found %s topics links on forum" % len(self.topics_urls))

        # Save urls to file
        with open (os.path.join(self.output_dir, "urls.txt"), 'w') as filey:
            filey.writelines('\n'.join(self.topics_urls))
       

    def get_thread_urls(self, thread_url):
        '''Given a thread, get all raw_urls for it.'''

        self.driver.get(thread_url)

        # Wait for Javascript to load
        try:
            WebDriverWait(self.driver, 3).until(lambda d: False)
        except TimeoutException:
            pass

        message_ids = self._get_all_message_ids()

        raw_urls = [
            self._get_raw_url(thread_url, message_id)
            for message_id in message_ids
        ]

        if self.verbose:
            print('Thread %s: %s raw urls.' % (thread_url, len(raw_urls)))

        return raw_urls


    def scroll_to_bottom(self):
        '''we could target an element at the bottom, but the easiest thing to
           do is to ask the user to scroll until he/she hits the bottom,
           and press enter.
        '''
        input("Scroll to the bottom (the first post) and press Enter to continue...")


    #### Topic Functions ######################################################

    def _get_all_message_buttons(self):
        '''Return all the message buttons on the page.'''

        timeline = self.driver.find_element_by_id('tm-tl')
        all_buttons = timeline.find_elements_by_class_name(
            'jfk-button-standard'
        )

        return all_buttons

    def _get_all_message_ids(self):
        '''Return all the message ids given a timeline with list of messages.
        '''
        all_buttons = self._get_all_message_buttons()
        message_buttons = [
            el for el in all_buttons
            if el.get_attribute('aria-label').startswith('More')
        ]
        message_ids = [
            button.get_attribute('id')[len('b_action_'):]
            for button in message_buttons
        ]

        return message_ids

    def _get_raw_url(self, thread_url, message_id):
        '''Given the thread_url and the message_id, return the raw message url
        '''
        _, group, thread_id = thread_url.rsplit('/', 2)
        url_fmt = ('https://groups.google.com/%s/forum/message/raw?msg=' % self.org) + '%s/%s/%s'

        return url_fmt % (group, thread_id, message_id)


    #### Private interface ####################################################

    def _get_driver(self):
        '''Get the web-driver for the scraper, the chromedriver should be
           added to the path.
        '''

        driver = webdriver.Chrome()
        driver.implicitly_wait(30)

        return driver

    def _save_content_of_message(self, url):
        ''' Given a url to a raw text of a post, save it to file.
            We save to the output folder under topics/thread_id/message_id
        '''
        # <thread_id>/<message_id>
        thread_id, message_id = url.split('/')[-2:]
        dir_path = "%s%s%s.txt" %(self.export_dir, os.path.sep, thread_id)

        # Create directory for the thread
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        # Don't do the request if the file exists
        file_path = os.path.join(dir_path, "%s.txt" % message_id)

        if not os.path.exists(file_path):
            message = requests.get(url).text
 
            # Note that these messages have all kinds of newlines /r/n
            with open(file_path, 'w') as filey:
                filey.writelines(message)


# Helper Functions

def add_driver_topath():
    os.environ['PATH'] = "%s:%s" %(get_here(), os.environ['PATH'])

def get_here():
    return os.path.abspath(os.path.dirname(__file__))

def get_parser():
    parser = argparse.ArgumentParser(description="Google Group Scraper")
    parser.add_argument('org', 
                        help="the name the organization (e.g., a/lbl.gov)", 
                        nargs=1)

    parser.add_argument('group', 
                        help="the name of the Google Group (e.g., singularity)", 
                        nargs=1)

    return parser


if __name__ == "__main__":

    add_driver_topath()

    parser = get_parser()
    args, extra = parser.parse_known_args()

    # We won't get here if positional args not provided
    scraper = GoogleGroupsScraper(organization=args.org[0],
                                  group_name=args.group[0],
                                  verbose=True)
    scraper.save_all_posts()
