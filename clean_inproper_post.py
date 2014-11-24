# -*- coding: utf-8 -*-

""" Delete posts on MitBBS that contains dirty/inproper words

    The program is only compatible with Python (>=3.2.0)

    The program will:
    1. login to http://www.mitbbs.com/
    2. scan through each post of a page:
       - if the main post (first post) contains dirty/inproper words, delete the entire post
       - if any comment contains dirty/inproper words, delete that comment
       - if error occurs, move to the next post 
    3. @TODO: log all changes with userid|post content

    Depends:
       - BeautifulSoup4
       - requests
    
    Author: Yue Zhao (yzhao0527 [a t] gmail [d o t] com)
    Date:   2014-10-12
"""
import re, sys
from bs4 import BeautifulSoup
import requests
# from snownlp import SnowNLP
from time import gmtime, strftime


# ===== User configuration =====
# import USERID and PASSWD from a file called userID.py
# from userID import *
USERID   = 'your username'
PASSWD   = 'your pwd'
#URL      = "http://www.mitbbs.com/bbsdoc/NewYork.html"
URL      = "http://www.mitbbs.com/club_bbsdoc2/letsgo_0.html"
club = False #Indicate whether a URL is of a club or not
if "club_bbsdoc" in URL:
    club = True

DICTFILE = "wordDict.txt" # each line is treated as one word and converted to lower case.
MAX_DELETE_NUMBER = 10 # Maximum number of posts that can be deleted.

#wordList = ['goood']

# ===== End of User configuration =====

# load the dirty word list
with open(DICTFILE, "r", encoding="utf-8") as f:
    wordList = [w.lower() for w in [w.strip() for w in f.readlines()] if len(w) > 0]

# wordList = ["NYC", "Quant", "纽约", "问"] # Used this list to test the code MAX NUMBER IS REACHED.

# Find dirty words in the given text
# INPUT:
#        text: a string
#    wordList: a list of words to be searched for
# OUTPUT:
#    the first word in the list that appears in the text,
#    return None if no such word exists
# COMMENT:
#    consider using regex (import re) for fancy matching.
def findWord(text, wordList):
    text = text.lower()
    for w in wordList:
        if text.find(w) != -1:
            return w

# Parse Delete Button Arguments
# INPUT:
#    d: the html:<a> entry corresponding to the delete operation
# OUTPUT:
#    a list of 3 arguments used to delete a post
def parseDelOpts(d):
    t    = re.search(r'\(.*\)', d['onclick']).group(0)

    t    = t[1:-1]
    opts = t.split(',')
    opts[0] = opts[0][1:-1]
    return opts

# Parse Delete Button Arguments
# INPUT:
#    p: the content of a raw bbs post text
# OUTPUT:
#    the original post with title hided
def cleanPost(p):
    inx = p.find(u'发信站')
    return p[inx:]

# Delete a post
# INPUT:
#        d: data used to delete the post
#     opts: form data used to delete the post
#  cookies: cookies with login data
#      ask: interactive mode if true
# OUTPUT:
#      Boolean, whether the deletion operation succeeded
def deletePost(d, opts, cookies, ask=True):
    if ask:
        print("    Delete post? [y/n]", end=" ")
        ans = input()
        if len(ans) == 0:
            ans = 'n'
        ans = ans[0].lower()
        if ans != 'y':
            print("Post is NOT deleted.")
            return False
    delFormOpts = opts.copy()
    delFormOpts['file']     = d[0]
    delFormOpts['id']       = d[1]
    delFormOpts['dingflag'] = d[2]
    
    r = requests.post(r'http://www.mitbbs.com/mitbbs_bbsdel.php',
                      data=delFormOpts, cookies = cookies, allow_redirects=True)
    r.encoding = "gb2312"
    if r.text.find(r"删除成功") != -1: #@TODO: there must be a better way to do this
        print(r"succeed.")
        return True
    else:
        print(r"failed")
        return False
  
#Save a message
#INPUT: 
#    user: user id
#    post: post string
#Write the post in to a file named by the user id + current time
#    
def saveMessage(user, post):
    filename = user + strftime("%Y-%m-%d_%H:%M:%S", gmtime())
    f = open(filename,"w")
    f.write(post)
    f.close()

#Send a mail containing the deleted post to the author
#INPUT: 
#    user: user id
#    post: post string
#OUTPUT
#    Boolean, whether the mail was sent.
def sendMessage(user,post):
    mailbox = {'userid' : user, 'title' : 'Post deletion notice', 'text' : post}
    rMail = requests.post(r'http://www.mitbbs.com/mitbbs_bbssndmail.php', \
        data=mailbox, cookies = session.cookies, allow_redirects=True)
    rMail.encoding = "gb2312"
    if rMail.text.find(r"信件已成功发送") != -1: #@TODO: there must be a better way to do this
        return True 
    else: 
        return False   


#Get the edit information
def getEditInfo(elink):
    edit_re = requests.get("http://www.mitbbs.com" + elink["href"], cookies = session.cookies) # click Modify button
    edit_re.encoding = 'gb2312'
    edit_form_start = edit_re.text.find('<form name="form1"')
    edit_form_end = edit_re.text.find('</form>', edit_form_start)
    edit_form_str = edit_re.text[edit_form_start: edit_form_end + 7]  #7 is the length of '</form>'
    esoup = BeautifulSoup(edit_form_str)
    inputs = esoup.find_all("input")
    ops = {t['name'] : t['value'] if t.has_attr('value') else "" for t in inputs if t.has_attr('name')}
    return ops

#Post content using editops
def postEdited(content, editops):
    editops["text"] = content # the content of the modified post
    #pdb.set_trace()
    postResponse = requests.post(r"http://www.mitbbs.com/mitbbs_bbsedit_charge.php", data=editops, cookies=session.cookies, allow_redirects=True)

    postResponse.encoding = "gb2312"
    if postResponse.text.find(r"修改文章成功") != -1: #@TODO: there must be a better way to do this
        print(r"Edit post succeed.")
        return True
    else:
        print(r"Edit post failed.")
        return False



# login to http://www.mitbbs.com
auth = {'id' : USERID, 'passwd' : PASSWD, 'kick_multi' : '1'}
session = requests.session()
session.post("http://www.mitbbs.com/newindex/mitbbs_bbslogin.php", data=auth)
n_deleted = 0 # Counter used to count how many posts have been deleted

# ========= START PARSING WEBPAGE DATA ==========

# fetch webpage and make 'a beautiful soup'
r   = requests.get(URL, cookies=session.cookies)
r.encoding = "gb2312"

soup = BeautifulSoup(r.text)

# C. parse each article
if club:
    items = soup.find_all('a', href=re.compile('clubarticle'))
else:    
    itemHolder = soup.findAll('td', {'class' : 'taolun_leftright'})
    items      = itemHolder[0].findAll('a', {'class' : 'news1'})



for n, item in enumerate(items):

    if n_deleted >= MAX_DELETE_NUMBER:
       break

    if n % 10 == 9:
       print("Processed {} posts".format(n + 1))
    
    title = item.text.strip()


    link  = r'http://www.mitbbs.com/' + item['href']
    
    try:

        # Read the content of a post
        r     = requests.get(link, cookies=session.cookies)
        r.encoding = "gb2312"
        soup  = BeautifulSoup(r.text)
        
        boxes = [u.parent for u in soup.findAll("td", {"class" : "wenzhang_bg"})]
        users = [b.find('a').text.strip() for b in boxes]
        posts = [b.find('td', {"class" : "jiawenzhang-type"}) for b in boxes]
        delButtons = [b.find("a", text=u"删除") for b in boxes]
        editLink = [b.find("a", text=u"修改") for b in boxes] # list of Modify links of the post on the page

        # Data quality check
        # @TODO: Error is not handled
        for u, p, d in zip(users, posts, delButtons):
            if u == None or p == None or d == None:
                raise Exception("content error: None returned for user/post/delButton.")
        
        posts   = [cleanPost(p.text) for p in posts]
        delOpts = [parseDelOpts(d) for d in delButtons]
        
        # Parse delete form
        delForm      = soup.find("form", {'name' : 'delform'})
        delFormItems = delForm.findAll('input')
        delFormOpts  = {t['name'] : t['value'] if t.has_attr('value') else '' for t in delFormItems}
        
        # Scan through each post

        for i, (u, p, d, el) in enumerate(zip(users, posts, delOpts, editLink)):
            
            deleteThisPost = False
            info    = [] # I used a list in case that one needs to put in more text

            found = findWord(p, wordList)
            if found != None:
                if i == 0: # The first article is treated as the main article
                    deleteThisPost = True
                    info.append("The main article contains: " + found)
                else:      # All other articles are treated as comments
                    info.append("         A reply contains: " + found)
                    pureReply = p.split("的大作中提到")[0]  + "的大作中提到：】"
                    pureReply = pureReply[pureReply.find('\n') + 1:] # start from the second line, b/c the first line is 发信站...
                    #print("pureReply is " + pureReply)
                    replyFound = findWord(pureReply, wordList)
                    if replyFound is not None: # Pure Reply contains dirty
                        print("Pure Reply contains dirty")
                        deleteThisPost = True
                    else: # Pure Reply does not contain dirty but original reply contains dirty, need modification
                        print("Editing post")
                        editops = getEditInfo(el) # el is the edit link for original post
                        new_content = pureReply
                        print("new_content is '" + new_content + "'")
                        editReturn = postEdited(new_content,editops)

            if deleteThisPost: # @TODO: add more criteria
               print("   Dirty word Found in post: " + title)
               print("      " + info[0])

               deleteReturn = deletePost(d, delFormOpts, cookies=session.cookies, ask=True)
            # deleteReturn = True # This line is used for test. Meanwhile commented deleteReturn.

               if deleteReturn:
                   n_deleted = n_deleted + 1
                   if n_deleted >= MAX_DELETE_NUMBER:
                      print("MAX_DELETE_NUMBER reached")
                      break

                #Currently, the following action cannot be done with the test account
                #sendMessage(u,p)

    except Exception as e:
        print("Error occurred {} for {}.".format(str(e), title))

print("done")
