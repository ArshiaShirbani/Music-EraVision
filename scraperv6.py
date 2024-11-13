from imslp.interfaces.scraping import fetch_category_table
from playwright.sync_api import sync_playwright
import urllib
from bs4 import BeautifulSoup, NavigableString, Tag
import requests
import os
import random
import time
import fitz

def run(playwright, composerUrl):
    browser = playwright.chromium.launch()  # You can change chromium to firefox or webkit if needed

    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    page = context.new_page()

    retries = 1
    max_retries = 10
    while retries <= max_retries:
        try:
            page.goto(composerUrl)       
        except:
            time.sleep(2)
            print(f'Failed to connect to IMSLP, trying again:{retries}')
            retries += 1
            continue
        break

    all_page_contents = []

    all_page_contents.append(page.content())


    n = 0

    while True:
        try:
            page.click('a.categorypaginglink:has-text("next")') 
    
            # Wait for the new content to load (optional but often needed)
            page.wait_for_selector("body")  # Replace 'some-element-on-the-next-page' with an element you expect to see on the next page
        
            all_page_contents.append(page.content())
        except:
            break



    # Close the browser
    context.close()
    browser.close()

    return(all_page_contents)


def download_compositions_of_composer(composer_name, num_compositions=10):
    # Ensure a directory exists to store the PDFs
    directory_name = composer_name.replace(" ", "_")
    if not os.path.exists(directory_name):
        os.makedirs(directory_name)

    # Constructing the URL for the composer
    composerTemplateUrl = "https://imslp.org/wiki/Category:"
    composerUrl = composerTemplateUrl + composer_name.replace(",", "%2C").replace(" ", "_")

    # Getting list of compositions
    #response = requests.get(composerUrl)

    with sync_playwright() as p:
        response = run(p, composerUrl)


    songDivs = []
    # Parse the HTML using BeautifulSoup
    for page in response:

        soup = BeautifulSoup(page, 'html.parser')

        elements = list(soup.descendants)
    
    # Define the start and stop phrases
        start_phrase = "Compositions by:"
        stop_phrases = {
            "Collaborations with:", "Pasticcios by or with:", "Collections by or with:",
            "Arrangements by:", "Works copied by:", "Works dedicated to:", "Books by:"
        }
    
    # Flags to control the search
        start_search = False
    

    # Iterate over all elements
        for el in elements:
        # If the element is a NavigableString, check for the start_phrase and stop_phrases
            if isinstance(el, NavigableString):
                if start_phrase in el:
                    start_search = True
                elif any(phrase in el for phrase in stop_phrases):
                    break  # If any stop phrase is encountered, stop the search

        # If we are in the search mode, look for <a> tags with the class "categorypagelink"
            if start_search and isinstance(el, Tag) and el.name == 'a' and 'categorypagelink' in el.get('class', []):
                songDivs.append(el)

    #soup = BeautifulSoup(response.text, 'html.parser')
    #songDivs = soup.find_all("a", {"class": "categorypagelink"})

    # Extracting song links from the composer's page
    songLinkArray = [song.get("href") for song in songDivs]

    # Randomly selecting compositions
    selected_songs = random.sample(songLinkArray, min(num_compositions, len(songLinkArray)))

    templatePDFURL = "https://s9.imslp.org/files/imglnks/usimg/"

    for song_link in selected_songs:
        songUrl = "https://imslp.org" + song_link

        response = requests.get(songUrl)
        soup = BeautifulSoup(response.text, 'html.parser')

        #sheetMusicArray = soup.find_all("div", {"class": "we"})


        # Find the span with id "wpscoresection"
        score_section = soup.find('span', id='wpscoresection')
    
        if not score_section:
            return "The starting section was not found."
    
        # Initialize an empty list to store the found div elements
        sheetMusicArray = []
    
    
        # Start iterating through the following siblings of the score_section span
        for sibling in score_section.find_all_next():
            # If the sibling is one of the stop search IDs, break the loop
            if isinstance(sibling, Tag) and sibling.get('id') in {'tabscore2', 'tabscore3', 'tabscore4', 'tabscore5', 'tabscore6', 'tabArrTrans'}:
                break
        
        # If the sibling is a div with class "we", add it to the list
            if sibling.name == 'div' and 'we' in sibling.get('class', []) and sibling.find(string="Complete Score"):
                sheetMusicArray.append(sibling)

        

        n = 1

        random.shuffle(sheetMusicArray)

        for sheetMusic in sheetMusicArray:
            if(n<=5):
                try:
                # Extracting the IMSLP ID of the pdf

                    IMPIndexStart = str(sheetMusic).find("IMSLP")
                    IMPIndexEnd = str(sheetMusic)[IMPIndexStart:].find("\"") + IMPIndexStart
                    IMPId = str(sheetMusic)[IMPIndexStart:IMPIndexEnd]

                # Extracting the image url data
                    imageUrlStart = str(sheetMusic).find("/images/")
                    imageUrlEnd = str(sheetMusic)[imageUrlStart:].find("\"") + imageUrlStart
                    imageUrl = str(sheetMusic)[imageUrlStart:imageUrlEnd]
                    brokenImageUrl = imageUrl.split("/")

                # Setting up the PDF link
                    PDFurl = templatePDFURL + brokenImageUrl[2] + "/" + brokenImageUrl[3] + "/" + IMPId + "-" + brokenImageUrl[4]

                # Downloading the PDF with streaming
                    response = requests.get(PDFurl, stream=True)

                # Check if the content type is a PDF before saving
                    if response.headers.get('content-type') != 'application/pdf':
                        continue
                    
                    pdf_doc = fitz.open(stream = response.content, filetype = "pdf")

                    # Create directory for song 
                    dir_file_name = os.path.join(directory_name, song_link.replace("/wiki/", "").replace("%2C", ",").replace("_"," ")+ f' ({n})')
                    if not os.path.exists(dir_file_name):
                        os.makedirs(dir_file_name)

                    #save each page of song in PNG
                    # for pg_num in range(min(pdf_doc.page_count, 10)):
                    for pg_num in range(pdf_doc.page_count):
                        file_name = os.path.join(
                                                    directory_name,
                                                    song_link.replace("/wiki/", "").replace("%2C", ",").replace("_"," ")+ f' ({n})',
                                                    f'page_{pg_num + 1}.png'
                                                )
                        page = pdf_doc.load_page(pg_num)
                        image = page.get_pixmap()
                        image.save(file_name, "png")

                    pdf_doc.close()


                except Exception as e:
                    print(e)
                    pass
            n = n + 1

#download_compositions_of_composer("Beethoven, Ludwig van", 10)
#download_compositions_of_composer("Mozart, Wolfgang Amadeus", 10)
#download_compositions_of_composer("Schubert, Franz", 10)
#download_compositions_of_composer("Schubert, Franz", 10)
#download_compositions_of_composer("Chopin, Frédéric", 10)
#download_compositions_of_composer("Schumann, Robert", 10)
#download_compositions_of_composer("Brahms, Johannes", 10)
#download_compositions_of_composer("Wagner, Richard", 10)
#download_compositions_of_composer("Verdi, Giuseppe", 10)
download_compositions_of_composer("Berlioz, Hector", 3)
download_compositions_of_composer("Tchaikovsky, Pyotr", 10)
download_compositions_of_composer("Mendelssohn, Felix", 10)
download_compositions_of_composer("Dvořák, Antonín", 10)
download_compositions_of_composer("Puccini, Giacomo", 10)
download_compositions_of_composer("Strauss, Richard", 10)
download_compositions_of_composer("Smetana, Bedřich", 10)
download_compositions_of_composer("Lalo, Édouard", 10)
download_compositions_of_composer("Franck, César", 10)
download_compositions_of_composer("Saint-Saëns, Camille", 10)
download_compositions_of_composer("Fauré, Gabriel", 10)
download_compositions_of_composer("Mahler, Gustav", 10)
download_compositions_of_composer("Debussy, Claude", 10)
download_compositions_of_composer("Rimsky-Korsakov, Nikolay", 10)
download_compositions_of_composer("Rachmaninoff, Sergei", 10)
download_compositions_of_composer("Elgar, Edward", 10)


#download_compositions_of_composer("Méhul, Etienne Nicolas", 10)
#download_compositions_of_composer("Vanhal, Johann Baptist", 10)
#download_compositions_of_composer("Rosetti, Antonio", 10)
#download_compositions_of_composer("Kraus, Joseph Martin", 10)
#download_compositions_of_composer("Kozeluch, Leopold", 10)
#download_compositions_of_composer("Richter, Franz Xaver", 10)
#download_compositions_of_composer("Dittersdorf, Carl Ditters von", 10)
#download_compositions_of_composer("Cramer, Johann Baptist", 10)
#download_compositions_of_composer("Dussek, Jan Ladislav", 10)
#download_compositions_of_composer("Stamitz, Carl Philipp", 10)
#download_compositions_of_composer("Gossec, François Joseph", 10)
#download_compositions_of_composer("Sabbatini, Luigi Antonio", 10)

#Romantic Composers

#Ludwig van Beethoven
#Wolfgang Amadeus Mozart (transitional period)
#Franz Schubert
#Franz Liszt
#Frédéric Chopin
#Robert Schumann
#Johannes Brahms
#Richard Wagner
#Giuseppe Verdi
#Hector Berlioz
#Pyotr Ilyich Tchaikovsky
#Felix Mendelssohn
#Antonín Dvořák
#Giacomo Puccini
#Richard Strauss
#Bedřich Smetana
#Édouard Lalo
#César Franck
#Camille Saint-Saëns
#Gabriel Fauré
#Gustav Mahler
#Claude Debussy
#Nikolai Rimsky-Korsakov
#Sergei Rachmaninoff
#Edward Elgar

#Classical Composers 14-25

#Étienne Méhul
#Johann Baptist Vanhal
#Antonio Rosetti
#Joseph Martin Kraus
#Leopold Kozeluch
#Franz Xaver Richter
#Carl Ditters von Dittersdorf
#Johann Baptist Cramer
#Jan Ladislav Dussek
#Carl Stamitz
#François-Joseph Gossec
#Luigi Antonio Sabbatini