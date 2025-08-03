'''
Semantic parsing for pilot/controller communications

'''

from nltk.ccg import chart, lexicon

from pathlib import Path
import time
import re


# Read regular expressions from a file and collect some stats
# about defined categories----------------------------------


def read_regex(f_name, dRegexCategory, dRegexComplexity, 
                    dCategoryFrequency, dPlaceholderCategory, dCategoryPlaceholder, dPlaceholderNumber):
    """
    ## Regular expressions are used to map words/phrases for ATC communications into semantic 
    categories

    For flexibility we store data about word/phrases -> categories mapping in a text file ('regex.txt). 
    Example. Here we define set of strings that may be mapped into CALLSIGN category.

    ```
    #CALLSIGN

    r"\bSWA\d+\b"
    r"\bAAL\d+\b"
    r"\bUAL\d+\b"
    r"\bDAL\d+\b"
    r"\bcallsign\b"
    r"\bheavy\s+777\b"
    r"\bn\d+[a-z]*\b"
    r"\b(november)\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|niner)
    r"\b[a-z]\-[a-z]+"
    r"\b(?!\d{1,2}[lr])\d+[a-z]{1,3}\b"
    
    ```

    This function reads regex.txt file and returns some dictionaries with info about semantic 
    categories. 
    """
    
    f_in = open(f_name ,encoding = 'utf-8', errors = 'ignore')

    """
    *dRegexCategory* dictionary maps all regex from 'regex.txt into categories. Hence we can't have two
    or more identical regex in different categories - be careful adding new data into regex.txt file. 
    """

    category = ''
    regex = ''
    
    for record in f_in:
        
        if record.startswith('#'):
            category = record.strip(' #\n').upper()
        else:
            regex = record.strip(' \n').replace('r"','').replace('"','').lower()
            if regex != '':
                dRegexCategory[regex] = category

    f_in.close()

    """
    *dRegexComplexity* dictionary stores complexity of each regex from 'regex.txt' file.
    
    The problem is that same word/phrase may be part of different regex applicable to a given ATC
    communication. To determin the order we extract categories from a communication we starts with 
    most complex regex applicable to the communication (greedy approach).

    NOTE - we ignore here (?:...), (?!...) and (?<!...) in regex while calculating its complexity.
    
    *dCategoryFrequency* dictionary store information about all unique categories defind in 'regex.txt'.
    While we store info about number of regex mapped in give category we don't use this info yet.
    """
    
    for regex in dRegexCategory:

        clean_regex = re.sub(r'\(\?.*?\)', '', regex)

          
        a_regex = clean_regex.split('\\')
        dRegexComplexity[regex] = len(a_regex)

    # Frequency of each category
    
    for item in dRegexCategory:
        category = dRegexCategory[item]
        if category not in dCategoryFrequency:
            dCategoryFrequency[category] = 0
        dCategoryFrequency[category] = dCategoryFrequency[category] + 1

    """
    *dPlaceHolderNumber*
    Placeholders for all categories - we use placeholders instead of real word/phrases 
    extracted from communication using a regex. For example both 'roger'and 'wilco' will be replaced
    by placeholed 'acknowledgeX' where X is an integer from 1..N where N is total number of occurences of words 'roger' and 'wilco'
    in the communication.

    This gives us possibility to significantly reduce size of the lexicon and hence latency.

    We don't know in advance how many placeholders we will need to use for any given 
    communicationmay for any new communication but we need to fix maximum number of such place holder
    in advance separately for each category. 
    
    We can do this using *dPlaceholderNumber* dictionary -- here we seе max number of placeholders for
    some categories and use small default value for all other categories. You may update these 
    settings. 


    """
    
    
    
    dPlaceholderNumber["CLOUDS"] = 6
    dPlaceholderNumber["FEATURE"] = 8
    dPlaceholderNumber["INTNUMBER"] = 9
    dPlaceholderNumber["PHONETICALPHABET"] = 6
    dPlaceholderNumber["REQUESTINSTRUCTION"] = 8
    dPlaceholderNumber["RUNWAY"] = 6
    dPlaceholderNumber["SIDE"] = 9
    dPlaceholderNumber["STATUS"] = 8
    dPlaceholderNumber["TO"] = 6
    dPlaceholderNumber["WORDNUMBER"] = 30
    
    dPlaceholderNumber["OTHER"] = 5 #default value

    """
    *dPlaceholderCategory* store categories of all placeholed that potentially may be extracted
    from any ATC communication. Please be careful - if a communication need to have more placeholder for e category
    that is give by *dPlaceHolderNumber* then correct parseing of the communication is impossible. 

    If you noticed such case in your data then please updated this function there max number of place holders
    is hardcoded. 
    """

    for category in dCategoryFrequency:
        dCategoryPlaceholder[category] = {}
        if category in dPlaceholderNumber:
            placeholder_number = dPlaceholderNumber[category] 
        else:
            placeholder_number = dPlaceholderNumber["OTHER"]

        for i in range(1, placeholder_number + 1):
            placeholder = category.lower()+str(i)
            dPlaceholderCategory[placeholder] = category
            dCategoryPlaceholder[category][placeholder] = 1



# make lexicon----------------------------------------------

def make_lexicon(dCategoryFrequency, dCategoryPlaceholder, a_prepositions, f_name, dCategoryFilter):

    """
    This fuction returns lexicon that is used by parser to parse ATC communications.

    Inputs:
    - dCategoryFrequeny -- dictionary with category names as keys and numbers of related 
    regex as values
    - dCategoryPlaceholdes -- dictionary with category names as keys and dictionary of related
    placeholders as values
    - a_prepositions -- array of prepositions that are outside of any category. Really the same proposition 
    may be represented by a category and be part of the list in the same time, but its in this case its representation in the
    list is ignored.
    - f_name -- name of a text file (lexicon_complex.txt) that contains data about sematic rules that can't be generated
    automatically. 
    - dCategoryFilter -- a dictionary with some category names. This make_lexicon function is 
    running 3 times to parse a communication. In first run we use dCategoryFilter = {}, while in 2nd 
    and 3rd runs it contains a non-empty set of category names. The I dea is to limit set of
    rules that are applicable in 2nd and 3rd runs.


    This is part of lexicon_complex.txt file that define some of 'complex' (not generated automaticall) 
    rules for lexicon related to CALLSIGN:

    ```
    #CALLSIGN
    -(CALLSIGN/FREQUENCY)/ON {\\x y._CALLSIGN_(_CALLSIGN_(callsign1), x,y)}
    (CALLSIGN/AIRFIELD)/AT {\\x y._CALLSIGN_(_CALLSIGN_(callsign1), x,y)}
    CALLSIGN/WORDNUMBER {\\x._CALLSIGN_(_CALLSIGN_(callsign1), x)}
    CALLSIGN/WORDNUMPHONEALPHABET {\\x._CALLSIGN_(_CALLSIGN_(callsign1), x)}
    (CALLSIGN/NAVIGATION)/IS {\\x y._CALLSIGN_(_CALLSIGN_(callsign1), x,y)}
    (CALLSIGN/STATUS)/IS {\\x y._CALLSIGN_(_CALLSIGN_(callsign1), x,y)}
    (CALLSIGN/FLIGHTPLAN)/IS {\\x y._CALLSIGN_(_CALLSIGN_(callsign1), x,y)}
    (CALLSIGN/PLACE)/AT {\\x y._CALLSIGN_(_CALLSIGN_(callsign1), x,y)}
    (CALLSIGN/POSITION)/IS {\\x y._CALLSIGN_(_CALLSIGN_(callsign1), x,y)}

    #AIRCRAFT
    CALLSIGN/CALLSIGN {\\x._CALLSIGN_(_AIRCRAFT_(aircraft1),x)}


    ```

    """

    #print('dCategoryFilter\n\n'+str(dCategoryFilter))
    
    # read lexicon complex file------------------------------------
    def read_lexicon_complex(f_name, dLexComplex):
        f_in = open(f_name ,encoding = 'utf-8', errors = 'ignore')

        category = ''
        lexicon_entry = ''
        placeholder = ''
        
        for record in f_in:
            if record.strip(' \t\n') == '':
                continue
            if record.startswith('#'): #category name 
                category = record.strip(' #\n').upper()
                # we generate here semantic rules for 1st placeholder of the category. Identical
                #rules for other placeholders for same category will be added to the lexicon 
                # on the final step 
                placeholder = category.lower()+'1'
                # dictionary to store 'complex' rules for each category (represented by its placeholder) 
                dLexComplex[placeholder] = []
            else: # just 'complex' rule
                if record.startswith('-'): # skip rule if starts with '-'
                    continue
            
                lexicon_entry = record.strip(' \n').replace('\\\\','\\')

                if dCategoryFilter == {}:
                    dLexComplex[placeholder].append(lexicon_entry)
                else:
                    good_entry = False
                    for good_category in dCategoryFilter:
                    
                        if lexicon_entry.lower().find('/'+good_category.lower()+' ') >= 0:
                            good_entry = True
                            break
                    if good_entry == True:
                        dLexComplex[placeholder].append(lexicon_entry)
                    
                

        f_in.close()
    
        
    # generate some rules for lexicon for a given category that are not 'comples' and
    # may be generated automatically
    def make_lex_all_category(category, dCategoryPlaceholder):
        """
        This function generate lexicon rules that are not complex and may be generated automaticall.

        For example, for category 'CALLSIGN' these rules will be generated:

        ```
        callsign1 => CALLSIGN {_CALLSIGN_(callsign1)}
        callsign2 => CALLSIGN {_CALLSIGN_(callsign2)}
        ...
        ```
        Here for each placeholder (callsign1, callsign2, ...) up to maximum number of placeholeders
        assigned to the category CALLSIGN we define a rule with syntactic and semantic parts. Here 
        category CALLSIGN defin the syntactic part while function _CALLSIGN_(callsignX) its semantic part.

        """
        res = ""
        for placeholder in dCategoryPlaceholder[category]:
            res = res + str(placeholder) + " => "+category.upper()+" {_"+category.upper()+'_('+str(placeholder)+")}\n"
            
        return(res)
    
    # generate 'complex' rules
    def make_lex_complex(dLexComplex, dCategoryPlaceholder):
    
        res = ""
        for placeholder in dLexComplex:
            a_ccg = dLexComplex[placeholder]
            #category name may be extracted from placeholder name
            category = placeholder.replace('1','').upper()
            # jst replace 1st placeholder from a rule from dLexComplex with all other placeholder related 
            # to related category
            for lex in a_ccg:
                for placeholder_new in dCategoryPlaceholder[category]:
                    res = res + placeholder_new + " => "+lex.replace(placeholder,placeholder_new)+"\n"
            
        return(res)

    # rules, generate automatically for prepositions
    def make_lex_preposition(dCategoryFrequency,  a_prepositions):
        """
        Let's we have this phrase in an ATC communication: '... the localizer ...'. 'localizer'
        belongs to the category 'NAVAID'. We want the same be true for phrase 'the localizer' where
        'the' is preposition. 
        
        Also if
        a word/phrase is unknown (doesn't belong to any category or the list of prepositions) then we assign it automatically to the lexical 
        category NP to such word/phrase. So for example word 'abracadabra' belongs to NP. We want the same is true for phrase
        'the abaracadabra'.

        So for 'the' we want to have automatically generated rules:

        ```
        the => NAVAID/NAVAID {\\x._the_(x)}
        ```
        for all categories including NAVAID, and

        ```
        the => NP/NP {\\x._the_(x)}
        ```
        for all unknown words/phrases.

        """


        res = ""
        for category in dCategoryFrequency:
            for preposition in a_prepositions:
                res = res + preposition + " => "+category+"/"+category+" {\\x._"+preposition+r"_(x)}"+"\n"
        for preposition in a_prepositions:
            res = res + preposition + " => NP/NP {\\x._"+preposition+r"_(x)}"+"\n"

            
            
        return(res)
    
    # first line in the lexicon - lex_categories ----------------

    """
    To generate a lexicon using NLTK we need to prepare a string with information about all
    rules we want to include into the lexicon. But it should starts with list of all categories.
    This list starts with categories common to any application that uses NLTK CCG parser: 
    """
    
    lex_categories = ":- S,NP,N,ADJ,VP,PP,P,JJ,JJR,DT,PPN,NNP\n"

    """
    Then we need to add all categories that we defined in 'regex.txt':
    """

    for category in sorted(dCategoryFrequency):
        lex_categories = lex_categories.strip('\n')+','+category.upper()
    lex_categories = lex_categories+'\n'
    

    # lex_common ------------------------------------------------

    """
    These are few special rules that we want to add to the lexicon. Rules for string '_context_'
    are used in a trick that we use to guaranty that parsing process will stop. Please not that in the 
    case of long sentence we can't guarantee that parsing process will stop with a result. It may be just empty set of results.
    To avoid this we do some modifications of the original sentence (including its spliting) to
    get something useful in all cases.

    Rules for 'no' are basis to introduce negation to the system.
    """

    lex_common = '''

    _context_ => (S/S)/NP {\\x y._context_(x,y)}
    _context_ => (S/NP)/S {\\y x._context_(x,y)}
    _context_ => S/NP {\\z._context_(z)}
    
    no => S/NP {\\z._no_(z)}
    no => S/S {\\z._no_(z)}

    '''

    
    for category in sorted(dCategoryFrequency):
        
        lex_common = (lex_common+'\n'+
            
            '_context_ => (S/S)/'+category.upper()+' {\\x y._context_(x,y)}\n'+
            '_context_ => (S/'+category.upper()+')/S {\\y x._context_(x,y)}\n'+
            '_context_ => S/'+category.upper()+' {\\z._context_(z)}\n'
            )
    

        lex_common = (lex_common+'\n'+
            'and => '+category.upper()+'/'+category.upper()+' {\\x._AND_(x)})\n'
            )
        
    


    # update lexicom with simple rules for each placeholder

    lex_all_category = ''
    for category in dCategoryFrequency:
        lex_all_category = lex_all_category + make_lex_all_category(category, dCategoryPlaceholder)

    


    # lex_complex----------------------------------------------

    # read lexicon complex entries file
    dLexComplex = {}
    read_lexicon_complex(f_name, dLexComplex)

    #print(dLexComplex)

    lex_complex = make_lex_complex(dLexComplex, dCategoryPlaceholder)
    #print(lex_complex)


    #lex_prepositions ----------------------------------

    
    lex_prepositions = make_lex_preposition(dCategoryFrequency,  a_prepositions)
    #print(lex_prepositions)


    # lex_last_part-------------------------------------
    """
    We use these rules to represent all words/phaese not recognised by patterns in regex.txt and
    not included into preposition list by special CONTEXT category. For this category we use 10
    placeholders X1,...,X12   
    """

    lex_last_part = """
    
    X1 => CONTEXT {X1}
    X2 => CONTEXT {X2}
    X3 => CONTEXT {X3}
    X4 => CONTEXT {X4}
    X5 => CONTEXT {X5}
    X6 => CONTEXT {X6}
    X7 => CONTEXT {X7}
    X8 => CONTEXT {X8}
    X9 => CONTEXT {X9}
    X10 => CONTEXT {X10}
    X11 => CONTEXT {X11}
    X12 => CONTEXT {X12}
    
    
    """


    # finally --------------------------------------------

    """
    Now we can generate lexicon uning NLTK lexicon.fromstring() function where the single
    argiment is the concatination of strings of rules generated above.
    """

    lex = lexicon.fromstring(lex_categories + 
                                lex_common + 
                                lex_all_category +
                                lex_complex +
                                lex_prepositions +
                                lex_last_part, True)
    return lex



# use this to read communications from a text file
def read_test_communications(f_name):
    
    f_in = open(f_name ,encoding = 'utf-8', errors = 'ignore')
    a_communications = []

    for record in f_in:
        
        communication = record.strip('\n')
        a_communications.append(communication)

    f_in.close()
    return a_communications


# all phrases from lexicon  --------------------------------
'''
We need this to extract unknow phrases from a communication we want to parse
'''

def lex_words(lexicon, dLexWords):
    for x in str(lexicon).split('\n'):
        word = x.split('=>')
        dLexWords[word[0].strip()] = 1



# Extract categories defined by regex from a command and 
# replace by placeholders -----------------------
"""
The concept of placeholders is very important for the project. The idea is that in parsing time
we parse not original sentence but its variant where words/phrases are replaced by placeholders. 

The total number of unique placeholders is significantly smaller than total number of unique
words/phrases that we can see in atc communications. These means that lexicon, that we use in parsing is small 
also and hence the parsing process hase smaller latency.

These are examples of a ATC communication, corresponding string of placeholders and mapping of placeholders
back into words/phrases from original communication.

Original (A) communication (punctuation is removed):
```
Southwest 578 cleared to Atlanta via radar vectors then V222 to CRG then direct Climb and maintain 5000 expect 35000 ten minutes after departure Departure frequency 124.85 squawk 5263
```

Step 1 - placeholders:
```
aircraft1 intnumber1 cleared1 to1 place1 via1 radar1 then1 route1 to2 fix1 then2 direction1 altitudechange1 intnumber2 expect1 intnumber3 wordnumber1 timeminsec1 after1 departure1 departure2 frequency1 realnumber1 squawk1 intnumber4
```
Step 1 - placeholedrs replacements

```
aircraft1 : Southwest
intnumber1 : 578
cleared1 : cleared
to1 : to
place1 : Atlanta
via1 : via
radar1 : radar vectors
then1 :then
route1 : V222
to2 :to
fix1 : CRG
then2 :then
direction1 : direct
altitudechange1 : Climd and maintain
intnumber2 : 5000
expect1 : expect
intnumber3 : 35000
wordnumber1 : ten
timeminsec1 : minutes
after1 : after
departure1 : departure
departure2 : Departure
frequency1 : frequency
realnumber1 : 124.85
squawk1 : squawk
intnumber4 : 5263

```


Step 2 - placeholders:
```
callsign1 cleared1 via1 radar1 then1 then2 altitudechange1 expect1 time1 after1 departure1 squawk1

```
Step 2 -- placeholder replacements
```
callsign1 : _CALLSIGN_(_AIRCRAFT_(*Southwest*),_INTNUMBER_(*578*))
cleared1 : _CLEARED_(_CLEARED_(*cleared*),_TO_(*to*),_PLACE_(*Atlanta*))
via1 : _VIA_(*via*)
radar1 : _RADAR_(*radar vectors*)
then1 : _THEN_(_THEN_(*then*),_ROUTE_(_ROUTE_(*V222*),_TO_(*to*),_FIX_(*CRG*)))
then2 : _THEN_(_THEN_(*then*),_DIRECTION_(*direct*))
altitudechange1 : _ALTITUDECHANGE_(_ALTITUDECHANGE_(*Climb and maintain*),_INTNUMBER_(*5000*))
expect1 : _EXPECT_(_EXPECT_(*expect*),_INTNUMBER_(*35000*))
time1 : _TIME_(_WORDNUMBER_(*ten*),_TIMEMINSEC_(*minutes*))
after1 : _AFTER_(_AFTER_(*after*),_DEPARTURE_(*departure*))
departure1 : _DEPARTURE_(_DEPARTURE_(*Departure*),_FREQUENCY_(_FREQUENCY_(*frequency*),_REALNUMBER_(*124.85*)))
squawk1 : _SQUAWK_(_SQUAWK_(*squawk*),_INTNUMBER_(*5263*))
```

Step 3 placeholders"
```
callsign1 cleared1 then1 then2 altitudechange1 expect1 departure1 squawk1
```

Step 3 - placeholder replacements

```
callsign1 : _CALLSIGN_(_AIRCRAFT_(*Southwest*),_INTNUMBER_(*578*))
cleared1 : _CLEARED_(_CLEARED_(_CLEARED_(_CLEARED_(*cleared*),_TO_(*to*),_PLACE_(*Atlanta*))),_VIA_(*via*),_RADAR_(*radar vectors*))
then1 : _THEN_(_THEN_(*then*),_ROUTE_(_ROUTE_(*V222*),_TO_(*to*),_FIX_(*CRG*)))
then2 : _THEN_(_THEN_(*then*),_DIRECTION_(*direct*))
altitudechange1 : _ALTITUDECHANGE_(_ALTITUDECHANGE_(*Climb and maintain*),_INTNUMBER_(*5000*))
expect1 : _EXPECT_(_EXPECT_(_EXPECT_(_EXPECT_(*expect*),_INTNUMBER_(*35000*))),_TIME_(_TIME_(_TIME_(_WORDNUMBER_(*ten*),_TIMEMINSEC_(*minutes*))),_AFTER_(_AFTER_(_AFTER_(*after*),_DEPARTURE_(*departure*)))))
departure1 : _DEPARTURE_(_DEPARTURE_(*Departure*),_FREQUENCY_(_FREQUENCY_(*frequency*),_REALNUMBER_(*124.85*)))
squawk1 : _SQUAWK_(_SQUAWK_(*squawk*),_INTNUMBER_(*5263*))
```

"""



def text2placeholders(command, dRegexCategory, dRegexComplexity, dReplacement):
    """
    This function is used on step 1 to convert original communication (command) to string of
    placeholders. Information about categories is sttored in input dictionaries dRegexCategory, 
    dRegexComplexity. Output dictionary dReplacement store placeholder replacements with 
    words/phrases from command.
    """
    #dCategoryUsed = {}
    new_command = command
    dCategoryMaxPlaceholderNumber = {}
    
    """
    Here we extract words/phrases from command relevant to a regex from dRegexComplexity. We use
    gready approach - use most complex applicable regex first. Relevant word/phrase is replaced
    with placeholder -- category name expanded with integer number. 

    This is possible that the same word/phrase occurs if the command more than once. To have 
    one-to-one correspondance between placeholders and related words/phrases in dReplacement we use
    a trick -- because keys in dReplacement are just extracted words/phrases we guaranty uniqueness
    surrounding the word/phrase with unique number of open and close symbols '<' and '>'.
    """

    count = 0
    new_command_ok = True
    while new_command_ok:
        new_command_ok = False
        for pattern in sorted(dRegexComplexity, key=dRegexComplexity.get, reverse=True):
            if pattern == '':
                continue
            p = re.compile(pattern, re.I)
            iterator = p.finditer(new_command)
            
            for match in iterator:
                if match:
                    count += 1
                    category = dRegexCategory[pattern]
                    
                    if category not in dCategoryMaxPlaceholderNumber:
                        dCategoryMaxPlaceholderNumber[category] = 0
                    dCategoryMaxPlaceholderNumber[category] = int(dCategoryMaxPlaceholderNumber[category]) + 1
                    
                    id = int(dCategoryMaxPlaceholderNumber[category])
                    category_id = category.lower()+str(id)

                    

                    dReplacement[category_id] = ''
                    
                    if len(match.groups()) == 0:
                        
                        new_command = ('{0}'+'<'*count+'{1}'+'>'*count+'{2}').format(new_command[:match.span()[0]],
                                                    new_command[match.span()[0]:match.span()[1]],
                                                        new_command[match.span()[1]:])

                        new_command_ok = True
                        dReplacement[category_id] = '<'*count+match.group(0)+'>'*count
                        to_replace = '<'*count+match.group(0)+'>'*count
                        
                        new_command = re.sub(to_replace, category_id, new_command, count=1)
                        
                    else:

                        start = -1
                        end = -1
                        start = match.group(0).find(match.group(1))
                        if start >= 0:
                            end = start + len(match.group(1))

                            new_command = ('{0}'+'<'*count+'{1}'+'>'*count+'{2}').format(new_command[:match.span()[0] + start],
                                                        new_command[match.span()[0]+start:match.span()[0]+end],
                                                            new_command[match.span()[0]+end:])
                            new_command_ok = True

                            dReplacement[category_id] = '<'*count+match.group(1)+'>'*count
                            to_replace = '<'*count+match.group(1)+'>'*count
                            
                            new_command = re.sub(to_replace, category_id, new_command, count=1)
                    
                if new_command_ok == True:
                    break
            if new_command_ok == True:
                    break

    return new_command



def LF2placeholders(LF, dReplacement):

    
    """
    This function is used to generate placeholders on 2nd and 3rd steps. The difference is that here
    instead of original text of communication in English we have logical form (LF) that is result
    of semantic parsing on the 1st step.

    This is example of such LF after 1st step for communication
    (A) "Southwest 578 cleared to Atlanta via radar vectors then ...":

    ```
    _CALLSIGN_(_AIRCRAFT_(*Southwest*),_INTNUMBER_(*578*)); _CLEARED_(_CLEARED_(*cleared*),_TO_(*to*),_PLACE_(*Atlanta*)); _VIA_(*via*); _RADAR_(*radar vectors*); _THEN_(_THEN_(*then*),_ROUTE_(_ROUTE_(*V222*),_TO_(*to*),_FIX_(*CRG*))); _THEN_(_THEN_(*then*),_DIRECTION_(*direct*)); _ALTITUDECHANGE_(_ALTITUDECHANGE_(*Climb and maintain*),_INTNUMBER_(*5000*)); _EXPECT_(_EXPECT_(*expect*),_INTNUMBER_(*35000*)); _TIME_(_WORDNUMBER_(*ten*),_TIMEMINSEC_(*minutes*)); _AFTER_(_AFTER_(*after*),_DEPARTURE_(*departure*)); _DEPARTURE_(_DEPARTURE_(*Departure*),_FREQUENCY_(_FREQUENCY_(*frequency*),_REALNUMBER_(*124.85*))); _SQUAWK_(_SQUAWK_(*squawk*),_INTNUMBER_(*5263*));
    ```
    In this case we can split the LF by ';' into sequence of functions: CALLSIGN, CLEARED, ...
    We use names of these functions (category names) to generate placeholders : callsign1, cleared1, ...
    As replacement for placeholder callsign1 we use related function from LF - _CALLSIGN_(_AIRCRAFT_(*Southwest*),_INTNUMBER_(*578*)).

    In the end of step 2 we have new LF and use it to generate new sequence of placeholders and new LF
    in the step1. 


    """


    new_command = ''
    count = 0

    dCategoryMaxPlaceholderNumber = {}

    for LF_item in LF.split(';'):
        LF_item = LF_item.strip(' ')

        if LF_item == '':
            continue

        if LF_item.lower() == LF_item:
            LF_item = '_context_('+LF_item+')'

        a_items = LF_item.split('_(')
        category = ''

        for item in a_items:
            

            if item != item.lower() or item.find('context') >= 0:
                category = item.strip('_').lower()
                break
        
        if category == '':
            continue

        if category not in dCategoryMaxPlaceholderNumber:
            dCategoryMaxPlaceholderNumber[category] = 1
        else:
            dCategoryMaxPlaceholderNumber[category] = int(dCategoryMaxPlaceholderNumber[category]) + 1
        
        categoryID = category+str(dCategoryMaxPlaceholderNumber[category])

        new_command = new_command + categoryID+' '
        
        count += 1

        dReplacement[categoryID] = '<'*count+LF_item+'>'*count

    return new_command


# replace phrases that are outside of the lexicon with special placeholders X1, .... ---------------------

def replace_unknown_phrases(command, dLexWords, dReplacement, a_prepositions):
    """
    Given a string of placeholders (command) this is possible that it may stil contain normal 
    words/phrases (not placeholders and not propositions). This is possible if this word/phrase is
    outside lexicon (and list of prepositions) -- they are not covered by any regex . 
    We call such words/phrases as unknown
    and we want to replace them with special placeholders - X1, X2, ...

    This function just doing this returning a string placeholders where unknown phrases are 
    replaced with special placeholders. Please not that it still may contain normal words 
    but only some prepositions. Output dictionary dReplacement maps unknown phrases into special
    placeholeds X1, X2, ...

    TODO -- it seems we have a problem if two unknow phrases are identical - fix it!!!
    """


    # ----- clean command (with placeholders -- now we can do this) ---------------------
    command = command.replace(':','').replace(';','').replace(',','').replace('.','').replace('+','').lower()
    
    # command where words from lexicon are replaced with 'Y' -----
    command_no_lex = command

    for word in sorted(dLexWords):
        if word == '':
            continue
        pattern = word+r"\b"
        if pattern[0] not in {'-'}:
            pattern = r"\b"+pattern

        p = re.compile(pattern, re.I)
        iterator = p.finditer(command)
        for match in iterator:
            if match:
                
                if (match.group()).isalpha() and match.group() not in set(a_prepositions):
                    continue

                to_replace = match.group()+r"\b"
                if to_replace[0] not in {'-','+'}:
                    to_replace = r"\b"+to_replace

                to_replace = to_replace.strip('+')


                command_no_lex = re.sub(to_replace,r"Y", command_no_lex, count=1)
                
    # replace unknow phrases with X1, X2,...   
               
    aNoLex = command_no_lex.split('Y')


    dNoLex = {}
    for word in aNoLex:
        if len(word) == 0:
            continue
        dNoLex[word] = len(word)

    new_command = command
    

    id = 0
    for word in sorted(dNoLex, key=dNoLex.get, reverse=True):
    
    
        if word == '' or word == '?' or word == '+':
            continue
        word = word.strip(".,:; ")
        if word == '':  
            continue
        
    
        pattern = word+r"\b"
        if pattern[0] not in {'-'}:
            pattern = r"\b"+pattern

        p = re.compile(pattern, re.I)
        iterator = p.finditer(command)
        for match in iterator:

            if match:
                
                id += 1
                X_id = 'X'+str(id)

                to_replace = match.group(0)+r"\b"
                if to_replace[0] not in {'-','+'}:
                    to_replace = r"\b"+to_replace
                to_replace = to_replace.strip('+')

                new_command = re.sub(to_replace,X_id, new_command, count=1)
                
                dReplacement[X_id] = match.group(0)

                
         
    return new_command


# Main function to parse command ------------------------------------

def parse_segment(parser, segment, maxExpansions, dReplacement_1, dReplacement_2):
        """
        This function returns logical form (LF) given a link to parser and segment of a command
        we want to parse. Please note that if a command is long and we can't parse it using CCG
        then we try to split it into segments that while are semantically complete can be parsed.

        The problem is that the parser may return empty result even for segment. 
        This depends of lexicon (used in parser
        generation) and segment itself. To reduce the probability of such event we use a trick 
        -- expanding original segment with zero, one or more (up to maxExpansions) copies of 
        special string 
        '_context_' that we add in the very beginning of the segment. We start with zero copies
        and stop if number of copies achieved its maximum or if we got at least one succesful 
        parsing.

        LF that we got as result of parsing still contain placeholder instead of real words/phrases
        from the command. We use dictionary dReplacement_1 and d_Replacement_2 that should store
        correct replacements of these placeholders.
        """


        nExpansions = 0
        nParses = 0
        parses = []

    
        segment_expanded = segment
        while nExpansions <= maxExpansions and nParses == 0:
            
            if nExpansions > 0:
                segment_expanded = '_context_ '+ segment_expanded
            nExpansions += 1

            parses = list(parser.parse(segment_expanded.split()))
            nParses = len(parses)   
            
        if nParses == 0:
            return ''    
        else:
            
            LF = ''
            for t in parses:
                (token, op) = t.label()
                LF = str(token.semantics())
                break

            
            LF_replacement = LF
            
            
            for X in dReplacement_1:
                Y = dReplacement_1[X]
                LF_replacement = re.sub(r"\b"+X+r"\b",'*'+Y+'*', LF_replacement, count=1)
                
            for X in dReplacement_2:
                Y = dReplacement_2[X]
                LF_replacement = re.sub(r"\b"+X+r"\b",'*'+Y+'*', LF_replacement, count=1)
                
            LF_replacement = LF_replacement.replace('<','').replace('>','')
            
            
            return LF_replacement

def command_normalization (command):
    pattern = r"\b(re\-)[a-z]+"
    p = re.compile(pattern, re.I)
    iterator = p.finditer(command)
    for match in iterator:
        if match:
            #print('match:'+str(match))
            command = re.sub(match.group(1),"re", command, count=0)

    pattern = r"\b[a-z](\-)[a-z]+"
    p = re.compile(pattern, re.I)
    iterator = p.finditer(command)
    for match in iterator:
        if match:
            #print('match:'+str(match))
            command = re.sub(match.group(1),"=", command, count=0)


    pattern = r"\b\d+(\-)\d\b"
    p = re.compile(pattern, re.I)
    iterator = p.finditer(command)
    for match in iterator:
        if match:
            #print('match:'+str(match))
            command = re.sub(match.group(1),"", command, count=0)

    
    command = command.replace("; "," ").replace(": "," ").replace(", "," ").replace(". "," ").replace("? "," ").replace('—',' ').replace("-"," ").replace("=","-").replace("’","'").replace("O'","O")
    command = command.replace(",","")
    command = command.replace("I'd","i would").replace("it's","it is").replace("what's","what is").replace("that's","that is").replace("'s","").replace("'ve"," have").replace("'ll"," will").replace("'re"," are").replace(" a "," ")
    command = command.replace(r"\s+"," ").replace("+","")
    command = command.strip('.,?!\n”"')

    return command

def clean_LF(LF):
    """
    In some cases logical form that we generate in parsing process
    may be too complicated and we may have possibility to simplify it.
    """


    # delete unneeded '*' 
    LF = LF.replace('*_','_').replace(')*',')')

    # delete simple duplicated functions
    pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\']+\)))\)"
    p = re.compile(pattern, re.I)
    iterator = p.finditer(LF)
    for match in iterator:
        if match:
            
            to_replace = str(match.group())
            replace_by = str(match.group(2))
            LF = LF.replace(to_replace, replace_by)

    # delete simple duplicated functions such as _STAR_(_the_(_STAR_(...)))
    pattern = r"\b(_[a-z]+_)\(((_[a-z]+_\(\1\([\s\w\d\-\,\.\*\']+\)\)))\)"
    p = re.compile(pattern, re.I)
    iterator = p.finditer(LF)
    for match in iterator:
        if match:
            
            to_replace = str(match.group())
            replace_by = str(match.group(2))
            LF = LF.replace(to_replace, replace_by)

    # delete unneeded duplicated functions
    pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\'\(\)]+\)))\)"
    p = re.compile(pattern, re.I)
    iterator = p.finditer(LF)
    for match in iterator:
        if match:
            
            to_replace = str(match.group())
            replace_by = str(match.group(2))
            
            #check if replace_by is good in terms of brackets
            ok = True
            b_open = 0
            b_close = 0
            min_equal = 0

            a = list(replace_by)
            for s in a:
                if s == '(':
                    b_open += 1
                if s == ')':
                    b_close += 1
                if b_open < b_close:
                    ok = False
                    break
                if (b_open == b_close and
                    min_equal == 0 and
                    b_open > 0
                ):
                    min_equal = b_open

                if (min_equal > 0 and
                    (min_equal < b_open or min_equal < b_close)
                ):
                    ok = False
                    break
            if b_open != b_close:
                ok = False
            
            if ok == True:
                LF = LF.replace(to_replace, replace_by)

    return LF

def parse_command(parser, command, dRegexCategory, dRegexComplexity, dLexWords, a_prepositions, step):

    LF_final = ''

    dReplacement_1 = {}
    dReplacement_2 = {}
    command_new = ''

    if step == 1:
        new_command_1 = text2placeholders(command, dRegexCategory, dRegexComplexity, dReplacement_1)
        new_command_2 = replace_unknown_phrases(new_command_1, dLexWords, dReplacement_2, 
                                                a_prepositions)
        command_new = new_command_2
        
        pattern = r"\b(x)\d+\b"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(command_new)
        for match in iterator:
            if match:
                command_new = re.sub(match.group(1),"X", command_new, count=1)
    else:
        command_new = LF2placeholders(command, dReplacement_1)
        print('dReplacement_1_step2_3\n'+str(dReplacement_1))

    print('\nPLACEHOLDERS step '+str(step)+'\t'+command_new)


    # parse command with expansion -------------------------

    maxExpansion = 1
    
    LF_replacement = parse_segment(parser, command_new, maxExpansion, dReplacement_1, dReplacement_2)
    if LF_replacement != '':

        # replace function _context_() by its argument if it is another 
        pattern = r"\b_context_\(_(.+)\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement)
        for match in iterator:
            if match:            
                LF_replacement = LF_replacement.replace(str(match.group(0)), '_'+str(match.group(1)))
        
        if step > 1:
            LF_replacement = clean_LF(LF_replacement)
            
        
        LF_final = LF_final +LF_replacement+'; '
    else:
        # we need to split the sentence into segments

        max_segment_length = 7
        while len(command_new) > 0:
            command_new_words = command_new.split(' ')
            
            for j in range(len(command_new_words) - 1, -1, -1):
                if j > max_segment_length:
                    continue
                segment =  ' '.join(command_new_words[0:j+1])
                LF_replacement = parse_segment(parser, segment, maxExpansion, dReplacement_1, dReplacement_2)
                
                if LF_replacement != '':
                    # replace function _context_() by its argument if it is another function
                    pattern = r"\b_context_\(_(.+)\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement)
                    for match in iterator:
                        if match:
                            LF_replacement = LF_replacement.replace(str(match.group(0)), '_'+str(match.group(1)))

                    if step > 1:
                        LF_replacement = clean_LF(LF_replacement)
                        
                    LF_final = LF_final +LF_replacement+'; '
                    command_new = ' '.join(command_new_words[j+1:len(command_new_words)+1])   
                    break
                
                if LF_replacement == '' and j == 0:
                    command_new = ''

    if step > 1:
        LF_final = LF_final.replace('STOP_(','_(')            
        LF_final = LF_final.replace('\n*','')            
            
                        
    print('\nSEMANTICS step '+str(step)+':\t'+LF_final)
    return LF_final


#############################################################
#1 Read regular expressions from 'regex.txt' file to collect some stats
#   about defined categories 
#############################################################
regex_file_name = 'regex.txt'

dRegexCategory = {} 
dRegexComplexity = {}
dCategoryFrequency = {} 
dPlaceholderCategory = {} 
dCategoryPlaceholder = {}
dPlaceholderNumber = {}


read_regex(regex_file_name, dRegexCategory, dRegexComplexity, 
        dCategoryFrequency, dPlaceholderCategory, dCategoryPlaceholder,
        dPlaceholderNumber)




############################################################
#2 Read lexicon rules and prepositions ---------------------
############################################################
lex_file_name = 'lexicon_complex.txt'
a_prepositions = ['to','the','is','at','be','being','for','has','of','on','through','will','with','via','in','your',
                  'underneath','this','that','it','as','over','into','an','are','if','out','then','up','now','or','my','when','have']


dCategoryFilter = {}
"""
When generating lexicon we may control which rules from 'lex_complex.txt' to use.
If dCategoryFilter is empty than we use all rules. If it is not empty then we use only rules
where syntactic category contains '/X' where X is a key from dCategoryFilter. 
"""
lex = make_lexicon(dCategoryFrequency, dCategoryPlaceholder, a_prepositions, lex_file_name, dCategoryFilter)

dCategoryFilter = {
    'after':1,
    'around':1,
    'as':1,
    'at':1,
    'before':1,
    'by':1,
    'due':1,
    'if':1,
    'in':1,
    'is':1,
    'for':1,
    'from':1,
    'with':1,
    'of':1,
    'off':1,
    'out':1,
    'on':1,
    'then':1,
    'through':1,
    'to':1,
    'until':1,
    'upto':1,
    'via':1,
    'when':1,
    'while':1,
    'will':1,
    'approach':1,
    'approved':1,
    'directionmagnetic':1,
    'fix':1,
    'status':1,
    'time':1,
    'trafficpattern':1,
    'trafficcircuit':1,
    'restriction':1,
    'confirmation':1,
    'confirmed':1,
    'emergency':1,
    'heading':1,
    'database':1,
    'phoneticalphabet':1,
    'goaround':1,
    'cancelled':1,
    'report':1,
    
}
lex_step2_3 = make_lexicon(dCategoryFrequency, dCategoryPlaceholder, a_prepositions, lex_file_name, dCategoryFilter)



#####################################################################
#3 Read test communications
#####################################################################


communications = 'test_communication.txt'
a_commands = read_test_communications(communications)



#######################################################
# all words from lexicon
#######################################################

dLexWords = {} 
lex_words(lex, dLexWords)




#######################################################
#5 CCG parser
#######################################################


parser = chart.CCGChartParser(lex, chart.ApplicationRuleSet + chart.CompositionRuleSet)
parser_step2_3 = chart.CCGChartParser(lex_step2_3, chart.ApplicationRuleSet + chart.CompositionRuleSet)

#########################################################
#6  Output files
#########################################################

results = 'RESULTS.tsv'
f_out = open(results, 'w', errors='ignore')
f_out.write('#\tCommunication\tSemantics\n')


#################################################################
# Main loop
#################################################################


start_time = time.time()

count = 0
for command in a_commands:
    
    count += 1
    original_command = command
    
    

    print('\n'+str(count)+'====================================================================')
    print('COMMAND:\n'+str(original_command))
    
    command = command_normalization(command)

    ########################################################
    # STEP 1
    ########################################################

    
    LF_final_step1 = parse_command(parser, command, dRegexCategory, dRegexComplexity, dLexWords, a_prepositions, 1)
    LF_final_step2 = parse_command(parser_step2_3, LF_final_step1, dRegexCategory, dRegexComplexity, dLexWords, a_prepositions, 2)
    LF_final_step3 = parse_command(parser_step2_3, LF_final_step2, dRegexCategory, dRegexComplexity, dLexWords, a_prepositions, 3)
    

    '''
    ########################################################
    # STEP 2
    ########################################################

    dReplacement_1_step2 = {}


    new_command_1_step2 = LF2placeholders(LF_final, dReplacement_1_step2)
    #print('new_command_1_step2\t'+new_command_1_step2)
    print('dReplacement_1_step2\n'+str(dReplacement_1_step2))
    
    command_new = new_command_1_step2

    dReplacement_2_step2 = {}
    
    placeholders = command_new
    
    
    print('\nPLACEHOLDERS step 2\t'+command_new)

    # parse command with expansion -------------------------

    maxExpansion = 1
    

    LF_replacement_step2 = parse_segment(parser_step2_3, command_new, maxExpansion, dReplacement_1_step2, dReplacement_2_step2)
    
    
    
    if LF_replacement_step2 != '':

        #print('???'+LF_replacement_step2)

        # delete _context_ function if its argument is a function
        pattern = r"\b_context_\(_(.+)\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement_step2)
        for match in iterator:
            if match:
                
                to_replace = str(match.group())
                replace_by = '_'+str(match.group(1))
                LF_replacement_step2 = LF_replacement_step2.replace(to_replace, replace_by)

                
        
        # delete unneeded '*' 
        LF_replacement_step2 = LF_replacement_step2.replace('*_','_').replace(')*',')')

        # delete simple duplicated functions
        pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\']+\)))\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement_step2)
        for match in iterator:
            if match:
                
                to_replace = str(match.group())
                #print('to_replace:::'+to_replace)
                replace_by = str(match.group(2))
                #print('replace_by:::'+replace_by)
                
                LF_replacement_step2 = LF_replacement_step2.replace(to_replace, replace_by)

        # delete simple duplicated functions such as _STAR_(_the_(_STAR_(...)))
        pattern = r"\b(_[a-z]+_)\(((_[a-z]+_\(\1\([\s\w\d\-\,\.\*\']+\)\)))\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement_step2)
        for match in iterator:
            if match:
                
                to_replace = str(match.group())
                #print('to_replace:::'+to_replace)
                replace_by = str(match.group(2))
                #print('replace_by:::'+replace_by)
                
                LF_replacement_step2 = LF_replacement_step2.replace(to_replace, replace_by)




        # delete unneeded duplicated functions
        pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\'\(\)]+\)))\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement_step2)
        for match in iterator:
            if match:
                
                to_replace = str(match.group())
                #print('to_replace:::'+to_replace)
                replace_by = str(match.group(2))
                #print('replace_by:::'+replace_by)
                
                #check if replace_by is good in terms of brackets
                ok = True
                b_open = 0
                b_close = 0
                min_equal = 0

                a = list(replace_by)
                #print(a)
                for s in a:
                    if s == '(':
                        b_open += 1
                    if s == ')':
                        b_close += 1
                    if b_open < b_close:
                        ok = False
                        break
                    if (b_open == b_close and
                        min_equal == 0 and
                        b_open > 0
                    ):
                        min_equal = b_open

                    if (min_equal > 0 and
                        (min_equal < b_open or min_equal < b_close)
                    ):
                        ok = False
                        break
                if b_open != b_close:
                    ok = False
                
                #print(str(ok))

                if ok == True:
                    LF_replacement_step2 = LF_replacement_step2.replace(to_replace, replace_by)


        
        LF_final_step2 = LF_final_step2 +LF_replacement_step2+'\n '

        


    else:
        # we need to split the sentence into segments

        max_segment_length = 7

        while len(command_new) > 0:
            command_new_words = command_new.split(' ')
            
            for j in range(len(command_new_words) - 1, -1, -1):

                if j > max_segment_length:
                    continue
                segment =  ' '.join(command_new_words[0:j+1])
                
                LF_replacement_step2 = parse_segment(parser_step2_3, segment, maxExpansion, dReplacement_1_step2, dReplacement_2_step2)
                
                
                if LF_replacement_step2 != '':
                    
                    # delete _context_ function if its argument is a function
                    pattern = r"\b_context_\(_(.+)\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement_step2)
                    for match in iterator:
                        if match:
                            
                            to_replace = str(match.group())
                            replace_by = '_'+str(match.group(1))
                            LF_replacement_step2 = LF_replacement_step2.replace(to_replace, replace_by)

                         
                    
                    # delete unneeded '*' 
                    LF_replacement_step2 = LF_replacement_step2.replace('*_','_').replace(')*',')')

                    # delete simple duplicated functions
                    pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\']+\)))\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement_step2)
                    for match in iterator:
                        if match:
                            
                            to_replace = str(match.group())
                            #print('to_replace:::'+to_replace)
                            replace_by = str(match.group(2))
                            #print('replace_by:::'+replace_by)
                            
                            LF_replacement_step2 = LF_replacement_step2.replace(to_replace, replace_by)

                    # delete simple duplicated functions such as _STAR_(_the_(_STAR_(...)))
                    pattern = r"\b(_[a-z]+_)\(((_[a-z]+_\(\1\([\s\w\d\-\,\.\*\']+\)\)))\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement_step2)
                    for match in iterator:
                        if match:
                            
                            to_replace = str(match.group())
                            #print('to_replace:::'+to_replace)
                            replace_by = str(match.group(2))
                            #print('replace_by:::'+replace_by)
                            
                            LF_replacement_step2 = LF_replacement_step2.replace(to_replace, replace_by)



                    # delete unneeded duplicated functions
                    pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\'\(\)]+\)))\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement_step2)
                    for match in iterator:
                        if match:
                            
                            to_replace = str(match.group())
                            #print('to_replace:::'+to_replace)
                            replace_by = str(match.group(2))
                            #print('replace_by:::'+replace_by)
                            
                            #check if replace_by is good in terms of brackets
                            ok = True
                            b_open = 0
                            b_close = 0
                            min_equal = 0

                            a = list(replace_by)
                            #print(a)
                            for s in a:
                                if s == '(':
                                    b_open += 1
                                if s == ')':
                                    b_close += 1
                                if b_open < b_close:
                                    ok = False
                                    break
                                if (b_open == b_close and
                                    min_equal == 0 and
                                    b_open > 0
                                ):
                                    min_equal = b_open

                                if (min_equal > 0 and
                                    (min_equal < b_open or min_equal < b_close)
                                ):
                                    ok = False
                                    break
                            if b_open != b_close:
                                ok = False
                            
                            #print(str(ok))

                            if ok == True:
                                LF_replacement_step2 = LF_replacement_step2.replace(to_replace, replace_by)


                            
                    


            
                    LF_final_step2 = LF_final_step2 +LF_replacement_step2+'; '
                    command_new = ' '.join(command_new_words[j+1:len(command_new_words)+1])   
                    break
                
                if LF_replacement_step2 == '' and j == 0:
                    command_new = ''
                
                
            
    print('\nSEMANTICS step 2:\t'+LF_final_step2)


    #### 3 ???

    ########################################################
    # STEP 3
    ########################################################

    dReplacement_1_step3 = {}


    new_command_1_step3 = LF2placeholders(LF_final_step2, dReplacement_1_step3)
    #print('new_command_1_step3\t'+new_command_1_step3)
    print('dReplacement_1_step3\n'+str(dReplacement_1_step3))
    
    command_new = new_command_1_step3

    dReplacement_2_step3 = {}
    
    placeholders = command_new
    
    
    print('\nPLACEHOLDERS step 3\t'+command_new)

    # parse command with expansion -------------------------

    maxExpansion = 1
    

    LF_replacement_step3 = parse_segment(parser_step2_3, command_new, maxExpansion, dReplacement_1_step3, dReplacement_2_step3)
    
    
    
    if LF_replacement_step3 != '':

        #print('???'+LF_replacement_step3)

        # delete _context_ function if its argument is a function
        pattern = r"\b_context_\(_(.+)\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement_step3)
        for match in iterator:
            if match:
                
                to_replace = str(match.group())
                replace_by = '_'+str(match.group(1))
                LF_replacement_step3 = LF_replacement_step3.replace(to_replace, replace_by)

                
        
        # delete unneeded '*' 
        LF_replacement_step3 = LF_replacement_step3.replace('*_','_').replace(')*',')')

        # delete simple duplicated functions
        pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\']+\)))\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement_step3)
        for match in iterator:
            if match:
                
                to_replace = str(match.group())
                #print('to_replace:::'+to_replace)
                replace_by = str(match.group(2))
                #print('replace_by:::'+replace_by)
                
                LF_replacement_step3 = LF_replacement_step3.replace(to_replace, replace_by)

        # delete simple duplicated functions such as _STAR_(_the_(_STAR_(...)))
        pattern = r"\b(_[a-z]+_)\(((_[a-z]+_\(\1\([\s\w\d\-\,\.\*\']+\)\)))\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement_step3)
        for match in iterator:
            if match:
                
                to_replace = str(match.group())
                #print('to_replace:::'+to_replace)
                replace_by = str(match.group(2))
                #print('replace_by:::'+replace_by)
                
                LF_replacement_step3 = LF_replacement_step3.replace(to_replace, replace_by)




        # delete unneeded duplicated functions
        pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\'\(\)]+\)))\)"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(LF_replacement_step3)
        for match in iterator:
            if match:
                
                to_replace = str(match.group())
                #print('to_replace:::'+to_replace)
                replace_by = str(match.group(2))
                #print('replace_by:::'+replace_by)
                
                #check if replace_by is good in terms of brackets
                ok = True
                b_open = 0
                b_close = 0
                min_equal = 0

                a = list(replace_by)
                #print(a)
                for s in a:
                    if s == '(':
                        b_open += 1
                    if s == ')':
                        b_close += 1
                    if b_open < b_close:
                        ok = False
                        break
                    if (b_open == b_close and
                        min_equal == 0 and
                        b_open > 0
                    ):
                        min_equal = b_open

                    if (min_equal > 0 and
                        (min_equal < b_open or min_equal < b_close)
                    ):
                        ok = False
                        break
                if b_open != b_close:
                    ok = False
                
                #print(str(ok))

                if ok == True:
                    LF_replacement_step3 = LF_replacement_step3.replace(to_replace, replace_by)


        
        LF_final_step3 = LF_final_step3 +LF_replacement_step3+'\n '
        

        


    else:
        # we need to split the sentence into segments

        max_segment_length = 7

        while len(command_new) > 0:
            command_new_words = command_new.split(' ')
            
            for j in range(len(command_new_words) - 1, -1, -1):

                if j > max_segment_length:
                    continue
                segment =  ' '.join(command_new_words[0:j+1])
                
                LF_replacement_step3 = parse_segment(parser_step2_3, segment, maxExpansion, dReplacement_1_step3, dReplacement_2_step3)
                
                
                if LF_replacement_step3 != '':
                    
                    # delete _context_ function if its argument is a function
                    pattern = r"\b_context_\(_(.+)\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement_step3)
                    for match in iterator:
                        if match:
                            
                            to_replace = str(match.group())
                            replace_by = '_'+str(match.group(1))
                            LF_replacement_step3 = LF_replacement_step3.replace(to_replace, replace_by)

                         
                    
                    # delete unneeded '*' 
                    LF_replacement_step3 = LF_replacement_step3.replace('*_','_').replace(')*',')')

                    # delete simple duplicated functions
                    pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\']+\)))\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement_step3)
                    for match in iterator:
                        if match:
                            
                            to_replace = str(match.group())
                            #print('to_replace:::'+to_replace)
                            replace_by = str(match.group(2))
                            #print('replace_by:::'+replace_by)
                            
                            LF_replacement_step3 = LF_replacement_step3.replace(to_replace, replace_by)

                    # delete simple duplicated functions such as _STAR_(_the_(_STAR_(...)))
                    pattern = r"\b(_[a-z]+_)\(((_[a-z]+_\(\1\([\s\w\d\-\,\.\*\']+\)\)))\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement_step3)
                    for match in iterator:
                        if match:
                            
                            to_replace = str(match.group())
                            #print('to_replace:::'+to_replace)
                            replace_by = str(match.group(2))
                            #print('replace_by:::'+replace_by)
                            
                            LF_replacement_step3 = LF_replacement_step3.replace(to_replace, replace_by)



                    # delete unneeded duplicated functions
                    pattern = r"\b(_[a-z]+_)\(((\1\([\s\w\d\-\,\.\*\'\(\)]+\)))\)"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(LF_replacement_step3)
                    for match in iterator:
                        if match:
                            
                            to_replace = str(match.group())
                            #print('to_replace:::'+to_replace)
                            replace_by = str(match.group(2))
                            #print('replace_by:::'+replace_by)
                            
                            #check if replace_by is good in terms of brackets
                            ok = True
                            b_open = 0
                            b_close = 0
                            min_equal = 0

                            a = list(replace_by)
                            #print(a)
                            for s in a:
                                if s == '(':
                                    b_open += 1
                                if s == ')':
                                    b_close += 1
                                if b_open < b_close:
                                    ok = False
                                    break
                                if (b_open == b_close and
                                    min_equal == 0 and
                                    b_open > 0
                                ):
                                    min_equal = b_open

                                if (min_equal > 0 and
                                    (min_equal < b_open or min_equal < b_close)
                                ):
                                    ok = False
                                    break
                            if b_open != b_close:
                                ok = False
                            
                            #print(str(ok))

                            if ok == True:
                                LF_replacement_step3 = LF_replacement_step3.replace(to_replace, replace_by)


                            
                    


            
                    LF_final_step3 = LF_final_step3 +LF_replacement_step3+'; '
                    command_new = ' '.join(command_new_words[j+1:len(command_new_words)+1])   
                    break
                
                if LF_replacement_step3 == '' and j == 0:
                    command_new = ''
                
    LF_final_step3 = LF_final_step3.replace('STOP_(','_(')            
    LF_final_step3 = LF_final_step3.replace('\n*','')            
           
    print('\nSEMANTICS step 3:\t'+LF_final_step3)
    '''
    
    


    #################################################################
    # Make json results
    #################################################################

    #LF_final_step3

    print('\n\nJSON=============\n')

    sJSON = '{'+LF_final_step3.strip('\s\t\n').replace(';',',').replace('_(','\":{').replace('_','\"').replace(')','}').replace('*','\"')+'}'

    #clean the sJSON

    while True:
        sJSON_new = sJSON
        pattern = r"\{\"[\w\d\s\.\'\-]+\"\}" 
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
                
                to_replace = match.group()
                replace_by = to_replace.strip('{}')
                
                sJSON_new = re.sub(to_replace,replace_by, sJSON_new, count=1)

        if sJSON_new == sJSON:
            break
        else:
            sJSON = sJSON_new

    while True:
        sJSON_new = sJSON
        pattern = r"\,\s+\}" 
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
                
                to_replace = match.group()
                replace_by = '}'
                
                sJSON_new = re.sub(to_replace,replace_by, sJSON_new, count=1)

        if sJSON_new == sJSON:
            break
        else:
            sJSON = sJSON_new

    while True:
        sJSON_new = sJSON
        pattern = r"\s+\}" 
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
                
                to_replace = match.group()
                #print("===to_replace<<<"+to_replace+">>>")
                replace_by = '}'
                
                sJSON_new = re.sub(to_replace,replace_by, sJSON_new, count=1)

        if sJSON_new == sJSON:
            break
        else:
            sJSON = sJSON_new


    # delete simple duplicated functions: "xyz":{"xyz":{...}} -> "xyz":{...}
    while True:
        sJSON_new = sJSON

        pattern = r"(\"[a-z]+\"\:\{)(\1[\"\w\d\s\_\:\,]+\})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(2))
                #print('BBB:::'+replace_by)
                
                sJSON_new = re.sub(to_replace,replace_by, sJSON_new, count=1)

        if sJSON_new == sJSON:
            break
        else:
            sJSON = sJSON_new


    
    ########################################################################
    # merge 'the: "the":{"xyz":{...}} -> "the_xyz":{...}

    while True:

        pattern = r"\"the\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{0})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"the '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"the\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{1})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"the '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"the\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{2})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"the '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"the\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{3})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"the '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        

        break

    ############################################################
    # merge 'have: "have":{"xyz":{...}} -> "have_xyz":{...}

    while True:

        pattern = r"\"have\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{0})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"have '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"have\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{1})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"have '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"have\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{2})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"have '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"have\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{3})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"have '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        

        break

############################################################
    # merge 'your: "your":{"xyz":{...}} -> "your xyz":{...}

    while True:

        pattern = r"\"your\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{0})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"your '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"your\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{1})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"your '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"your\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{2})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"your '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"your\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{3})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"your '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        

        break

############################################################
    # merge 'are: "are":{"xyz":{...}} -> "are xyz":{...}

    while True:

        pattern = r"\"are\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{0})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"are '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"are\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{1})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"are '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"are\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{2})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"are '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"are\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{3})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"are '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        

        break


############################################################
    # merge 'over: "over":{"xyz":{...}} -> "over xyz":{...}

    while True:

        pattern = r"\"over\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{0})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"over '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"over\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{1})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"over '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"over\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{2})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"over '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"over\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{3})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"over '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        

        break


############################################################
    # merge 'be: "be":{"xyz":{...}} -> "be xyz":{...}

    while True:

        pattern = r"\"be\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{0})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"be '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"be\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{1})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"be '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"be\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{2})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"be '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"be\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{3})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"be '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        

        break


############################################################
    # merge 'an: "an":{"xyz":{...}} -> "an xyz":{...}

    while True:

        pattern = r"\"an\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{0})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"an '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"an\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{1})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"an '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"an\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{2})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"an '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        pattern = r"\"an\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{3})\}"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(sJSON)
        for match in iterator:
            if match:
            
                to_replace = str(match.group())
                #print('AAA:::'+to_replace)
                replace_by = str(match.group(1))
                #print('BBB:::'+replace_by)
                
                
                n_open = 0
                n_close = 0
                OK = True

                for s in replace_by:
                    
                    if s == '{':
                        n_open += 1
                    if s == '}':
                        n_close += 1
                    if n_close > n_open:
                        OK = False
                        break
                if n_open != n_close:
                    OK = False   
                
                if OK:
                    replace_by = '\"an '+replace_by[1:]
                    #print('CCC:::'+to_replace)
                
                    sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

        
        if sJSON_new != sJSON:
            sJSON = sJSON_new
            

        

        break


#update duplicate keys =============================

    dKeys = {}

    pattern = r"\"[a-z\s]+\":" 
    p = re.compile(pattern, re.I)
    iterator = p.finditer(sJSON)
    for match in iterator:
        if match:
            
            to_replace = match.group()
            to_replace_key = to_replace.split(' ')[-1]
            prefix = '"'
            if to_replace_key.startswith(prefix) == False:
                to_replace_key = '\"'+to_replace_key
            #print('XXX:::'+to_replace_key+'>')
            if to_replace_key not in dKeys:
                dKeys[to_replace_key] = 0
            id = int(dKeys[to_replace_key]) + 1
            dKeys[to_replace_key] = id
            replace_by = '\"'+to_replace.strip(':\"')+'_'+str(id)+'\":'
            
        sJSON = re.sub(to_replace,replace_by, sJSON, count=1)


    print(str(sJSON)+'\n\n')

    f_out.write(str(count)+'\t'+original_command+'\t'+str(sJSON)+'\n')


f_out.close()

