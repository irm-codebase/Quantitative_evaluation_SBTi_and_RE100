import pandas as pd
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import time
import random
from bs4 import BeautifulSoup

PATH = "/data/"
INFO = {"next link": ["div", "companySinglePagination__paginationWrapper--2m5Dj"],
        "rank": ["div", "companyTitle__rank--2SYbW"],
        "name": ["h1", "heading__graphikCond--38qNM companyTitle__title--3Bdrv"],
        "table": ["div", "info__wrapper--1CxpW"],
        "footnote": ["div", "info__footnote--210Yd"]}
ORDER = ['rank', 'country', 'headquarters', 'industry', 'ceo', 'website', 'type', 'ticker', 'revenues ($M)',
                 'profits ($M)', 'market value ($M)', 'employees', 'comment', 'url']


def scrap_g500(url="https://fortune.com/company/walmart/global500/", iterations=500, debug=False):
    """
    Web scraper for the Fortune G500 list. Fetches all the available information from the latest list and outputs a
    csv database file.
    :param url: URL of the first company to be scrapped. Links in the website will be used to move to the next company.
    :param iterations: number of companies to be scraped, always in rank order (that is how the website links them).
    :param debug: print nice text messages
    :return:
    """
    options = Options()
    options.headless = True
    data = {}
    driver = webdriver.Firefox(options=options)
    if debug:
        print("Dynamic web scraper successfully initialized")
    try:
        for i in range(iterations):
            # Fetch the website
            driver.get(url)
            time.sleep(10 + random.randint(0, 10))  # To get past scraping or DOS checks (probably useless)
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            # Initialize the Index for the dataframe with the name of the company
            element = soup.find(INFO["name"][0], class_=INFO["name"][1])
            name = element.contents[0].contents[0].contents[0].contents[0]
            data[name] = []

            # Rank
            element = soup.find(INFO["rank"][0], INFO['rank'][1])
            rank = int(element.contents[1].contents[0])
            data[name].append(rank)

            # Info table
            element = soup.find(INFO["table"][0], INFO['table'][1])
            if debug:
                print("Running table scraping for rank", rank, '-', name)
            for j in range(2, 13):
                if debug:
                    print(j, ' ', end='')
                try:
                    data[name].append(element.contents[j].contents[1].contents[0])
                except IndexError:
                    data[name].append(None)
            else:
                if debug:
                    print('\n')

            element = soup.find(INFO["footnote"][0], INFO["footnote"][1])
            try:
                data[name].append(element.contents[0])
            except IndexError:
                data[name].append(None)

            data[name].append(url)

            # Fetch next url to be obtained
            if i != iterations - 1:
                element = soup.find(INFO["next link"][0], class_=INFO["next link"][1])
                url = element.contents[1].contents[0].attrs['href']
    finally:
        driver.quit()
        if debug:
            print("Closing web scraper and saving database")
        dataframe = pd.DataFrame.from_dict(data, orient='index', columns=ORDER)
        dataframe.to_csv(PATH + "G500_scrap.csv")


def scrap_g500_sectors(url="https://fortune.com/global500/2020/search/", headless=True, debug=False):
    options = Options()
    options.headless = headless
    driver = webdriver.Firefox(options=options)
    if debug:
        print("Web driver initialized")

    data = {}
    try:
        driver.get(url)
        time.sleep(20)

        # Clean the annoying popups
        xpath_cookies = '//*[@id="truste-consent-required"]'
        driver.find_element_by_xpath(xpath_cookies).click()
        time.sleep(10)

        # Get a list of all the sectors
        sectors = driver.find_element_by_xpath('//*[@id="sector"]')
        sectors = sectors.text.split('\n')
        rows_drop_down = "/html/body/div[1]/div/main/div[3]/div[2]/div/div[2]/div/div[2]/span[2]/select/option[6]"
        driver.find_element_by_xpath(rows_drop_down).click()
        if debug:
            print("List of sectors obtained. Rows set to 100 to minimize iterations.")

        xpath_sector_select = "/html/body/div[1]/div/main/div[3]/div[1]/form/div[1]/div[1]/select/option[%i]"
        xpath_pages = "/html/body/div[1]/div/main/div[3]/div[2]/div/div[2]/div/div[2]/span[1]/span"
        xpath_next = "/html/body/div[1]/div/main/div[3]/div[2]/div/div[2]/div/div[3]/button"
        for i, sector in enumerate(sectors):
            driver.find_element_by_xpath(xpath_sector_select % (i+2)).click()
            time.sleep(10)
            pages = int(driver.find_element_by_xpath(xpath_pages).text)
            if debug:
                print("Page for", sector, "loaded. Total pages: ", pages)

            for page in range(pages):
                html = driver.page_source
                soup = BeautifulSoup(html, "html.parser")
                element = soup.find("div", class_='rt-tbody')

                for row in range(len(element.contents)):
                    values = element.contents[row]
                    company = values.contents[0].contents[1].contents[0].contents[0].contents[0].contents[0].contents[0]
                    if company in data:
                        data[company] = data[company]+sector
                    else:
                        data[company] = sector
                if debug:
                    print("Page", page+1, "completed")
                if page < pages-1:
                    driver.find_element_by_xpath(xpath_next).click()
                    time.sleep(10)
    finally:
        driver.quit()
        if debug:
            print("Closing web scraper and saving database")
        dataframe = pd.DataFrame.from_dict(data, orient='index', columns=['sector'])
        dataframe.to_csv(PATH + "G500_scrap_sectors.csv")


def combine_g500_sectors(csv_main, csv_sectors):
    main = pd.read_csv(PATH+csv_main, index_col=0, header=[0])
    sectors = pd.read_csv(PATH+csv_sectors, index_col=0, header=[0])

    # Fix some differences in the names
    as_list = main.index.to_list()
    for i, name in enumerate(as_list):
        if '’' in name:
            as_list[i] = name.replace('’', "'")
    main.index = as_list

    # combine and reorder
    combined = pd.concat([main, sectors], axis=1)
    columns = combined.columns.to_list()
    columns = columns[:3]+[columns[-1]]+columns[3:-1]
    combined = combined[columns]
    combined.to_csv(PATH+"G500_sector.csv")


def get_scraped_g500_database():
    """
    Simple wrapper to generate a scrapped G500 database, with sectors.
    Takes quite some time to finish.

    Keep in mind that this database needs some pruning. Issues are:
    Industry: duplicates with slight differences
    Sectors: duplicates with slight differences
    :return:
    """
    scrap_g500(debug=True)
    scrap_g500_sectors(headless=False, debug=True)
    combine_g500_sectors('G500_scrap.csv', 'G500_scrap_sectors.csv')