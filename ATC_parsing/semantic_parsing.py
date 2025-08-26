'''
Semantic parsing for pilot/controller commands

'''

from nltk.ccg import chart, lexicon
import re
from importlib.resources import files


def make_lexicon(dData):

    """
    Argument:
    - dData
    Output dictionary that shores all the data we need to parse ATC command.

    This fuction takes some predefined text files from DATA subfolder and generates lexicon, 
    parsers and some other data that are used in the parsing of ATC commands. Output is 
    dData dictionary with all we need for parsing. If you need to fix some errors in the parsing 
    of specific command then you may update these predifined files in DATA.

    """
    
    regex_file = files("ATC_parsing.data").joinpath("regex.txt").read_text()
    """
    ## Regex ##
    
    In the *regex.txt* files we store regular expressions that are used to extract phrases from ATC 
    commands that correspond to semantic categories related to ATC phraseology, places, waypoints,
    fixes, airlines and some other ATC concepts. You are free to update this file in your
    local copy of the library to 'localize' it to your needs.

    # Example #
    
    These are some example records from *regex.txt* that define *CALLSIGN* category:

    ```
    #CALLSIGN
    r"\bAAL\d+\b"
    r"\bcallsign\b"
    r"\bheavy\s+777\b"
    r"\bn\d+[a-z]*\b"
    r"\b(november)\s+(?:zero|one|two|three|four|five|six|seven|eight|nine|niner)
    r"\b[a-z]\-[a-z]+"
    r"\b(?!\d{1,2}[lr])\d+[a-z]{1,3}\b"

    ```    
    """

    lex_complex_file = files("ATC_parsing.data").joinpath("lexicon_complex.txt").read_text()
    """
    ## Lexicon ##
    Lexicon stores rules that are used by parser in the parsing process. Most of these rules are
    generated here automatically based, for example, on list of categories in *regex.txt*, but most
    advanced rules that correspond to specific patterns used in ATC commands should be defined
    in *lexicon_complex.txt* file. If you have a problem with the parsing of a command and you can't fix it
    through *regex.txt' update, then you may try to expand the set of rules in this file.
    
    # Example #
    ```
    #AIRCRAFT
    CALLSIGN/CALLSIGN {\\x._CALLSIGN_(_AIRCRAFT_(aircraft1),x)}
    ```
    Here we see a rule from the section that corresponds to the *AIRCRAFT* category. It says that phrase
    ```
    Cessna 123AB
    ```
    has *CALLSIGN* category because it starts with 'Cessna' from *AIRCRAFT* category followed by
    '123AB' from *CALLSIGN* category. And it logical form representation is
    ```
    _CALLSIGN_(_AIRCRAFT_(*Cessna*),_CALLSIGN_(*123AB*))
    ```

    """
    prepositions_file = files("ATC_parsing.data").joinpath("prepositions.txt").read_text()
    """
    The *prepositions.txt* file contains the list of standard prepositions. In the parsing process they play slightly
    different role compared to other words if only they are not assigned a special category in
    *regex.txt* as, for example, category *TO* for 'to' and 'into'.

    """
    category_filters_file = files("ATC_parsing.data").joinpath("category_filters.txt").read_text()
    """
    The *category_filters.txt* file plays an important role in parsing the most complicated ATC
    commands. In such cases, rules from *lexicon_complex.txt* can't extract long semantically 
    continuous segments from the command and, as a result, split it into a sequence of shorter segments. 
    
    We may fix this
    problem running parse process more than once. But we need to be careful here to filter out some 
    rules from  *lexicon_coplex.txt* that are not applicable in all steps except the very first one.
    In another case, some segments that are not semantically related may be merged into the same 
    segment.
    """

    def read_regex(regex_file, dData):
        """
        Arguments:
        - regex_file
        A string that contains all the data from *regex.txt* file,
        - dData
        We update this dictionary with the data extracted from *regex_file*.

        This function reads *regex.txt* file and stores some data in *dData* dictionary 
        """
        
        lines = regex_file.splitlines()

        dRegexCategory = {}

        """
        *dRegexCategory* dictionary maps all regexes from *regex.txt* into categories. Hence we can't 
        have two or more identical regexes in different categories - be careful adding new data into 
        *regex.txt* file. 
        """
        
        category = ''
        regex = ''
        
        for record in lines:
            
            if record.startswith('#'):
                category = record.strip(' #\n').upper()
            else:
                regex = record.strip(' \n').replace('r"','').replace('"','').lower()
                if regex != '':
                    dRegexCategory[regex] = category

        dData['regex_category'] = dRegexCategory            


        dRegexComplexity = {}

        """
        *dRegexComplexity* dictionary stores the complexity of each regex from 'regex.txt' file.
        
        Basically before we start parsing an ATC command we want to represent it as a sequence of 
        so called placeholders. Each placeholder is a category name with an integer index. 
        Here we use regexes to extract phrase applicable to a regex and then replace this phrase 
        by relevant placeholder. We repeat this process until all words/phrases are replaced 
        with placeholders (we use special placeholders for unknown words/phrases)
        
        The problem is that different regexes may be applicable to different **intersected** phrases. 
        Hence we need to determine an order of regexes we check if it is applicable or not.

        Here we use a greedy approach - check regexes starting from the most complex ones.
        
        """

        for regex in dRegexCategory:

            clean_regex = re.sub(r'\(\?.*?\)', '', regex)

            
            a_regex = clean_regex.split('\\')
            dRegexComplexity[regex] = len(a_regex)

        dData['regex_complexity'] = dRegexComplexity           

        
        dCategoryFrequency = {}
        """
        *dCategoryFrequency* - number of regexes for each unique category
        """

        for item in dRegexCategory:
            category = dRegexCategory[item]
            if category not in dCategoryFrequency:
                dCategoryFrequency[category] = 0
            dCategoryFrequency[category] = dCategoryFrequency[category] + 1

        dData['category_frequency'] = dCategoryFrequency            


        
        dPlaceholderNumber = {}

        """
        ## dPlaceHolderNumber ##

        We use placeholders instead of real words/phrases 
        extracted from a command using a regex. For example, regexes for words  'roger'and 'wilco' 
        have the same categoty *ACKNOWLEDGE* and they will be replaced
        by placeholders 'acknowledgeX' where X is an integer from 1..N where N is the total number of 
        occurences of words 'roger' and 'wilco'
        in the command.

        The use of placeholders instead of real words/phrases gives us the possibility to significantly
        reduce size of the lexicon and hence latency of the parsing process.

        We don't know how many placeholders we need to have for any new command 
        but we need to fix the maximum number of such placeholders
        in advance separately for each category. 
        
        We can do this using *dPlaceholderNumber* dictionary -- here we store max number of 
        placeholders for
        some categories and a small default value for all other categories. You may update these 
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

        dData['placeholder_number'] = dPlaceholderNumber           


        dCategoryPlaceholder = {}
        dPlaceholderCategory = {}

        """
        *dPlaceholderCategory* stores categories of all placeholders that potentially may be 
        extracted
        from any ATC command. Please be careful - if a command needs to have more placeholders 
        for a category
        than it is given by *dPlaceHolderNumber* then correct parsing of the command is impossible. 

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

        dData['category_placeholder'] = dCategoryPlaceholder            
        dData['placeholder_category'] = dPlaceholderCategory            

    
    def read_prepositions(prepositions_file, dData):
        """
        Arguments:
        - prepositions_file
        A string that contains all the data from *prepositions.txt* file,
        - dData
        We update this dictionary with the data extracted from *prepositions_file*.



        Read prepositions from *preposition_file*
        """
        
        lines = prepositions_file.splitlines()

        a_prepositions = []
        for record in lines:
            
            if record.strip(' #\n') == '':
                continue
            else:
                a_prepositions.append(record.strip(' #\n').lower())

        dData['prepositions'] = a_prepositions
        
    

    def read_category_filters(category_filters_file, dData):
        """
        Arguments:
        - category_filters_file
        A string that contains all the data from *category_filters.txt* file,
        - dData
        We update this dictionary with the data extracted from *category_filters_file*.


        Read category filters from *category_filters_file*
        """
        
        lines = category_filters_file.splitlines()
        
        dCategoryFilter = {}
        for record in lines:
            
            if record.strip(' \n') == '' or str(record).startswith('-') :
                continue
            else:
                dCategoryFilter[record.strip(' \n').upper()] = 1

        dData['category_filter'] = dCategoryFilter
    

    def read_lexicon_complex(lex_complex_file, dLexComplex, with_filter):
        """
        Arguments:
        - lex_complex_file
        A string that contains all the data from *lexicon_complex.txt* file,
        - dLexComplex
        Output dictionary with a set of rules from *lex_complex_file*.
        - with_filter
        May be 'True' or 'False'. If 'False' then all rules from 'lex_complex_file' are extracted.
        If 'False' then the extraction depends on a filter.

        Read rules from *lex_complex_file*. These rules will be stored in *dLexComplex* dictionary.
        If 
        ```
        with_filter == True
        ```
        then all rules from *lex_complex_file* will be stored in  *dLexXomplex*. In another case
        we store only rules that contain string '/X' where 'X' is a category from the category filter.

        """


        lines = lex_complex_file.splitlines()

        category = ''
        lexicon_entry = ''
        placeholder = ''
        
        for record in lines:
            if record.strip(' \t\n') == '':
                continue
            if record.startswith('#'): #category name 
                category = record.strip(' #\n').upper()
                placeholder = category.lower()+'1'
                """
                We generate here semantic rules for 1st placeholder of the category. Identical
                rules for other placeholders for same category will be added to the lexicon 
                on the final step. 
                """
                dLexComplex[placeholder] = []
                """
                dictionary to store 'complex' rules for each category 
                (represented by its placeholder) 
                """
            else: # just 'complex' rule
                if record.startswith('-'): # skip rule if starts with '-'
                    continue
            
                lexicon_entry = record.strip(' \n').replace('\\\\','\\')

                if not with_filter:
                    dLexComplex[placeholder].append(lexicon_entry)
                else:
                    good_entry = False
                    for good_category in dData['category_filter']:
                    
                        if lexicon_entry.lower().find('/'+good_category.lower()+' ') >= 0:
                            good_entry = True
                            break
                    if good_entry == True:
                        dLexComplex[placeholder].append(lexicon_entry)
                    
                  
    def make_lex_all_category(category):
        """
        Argument:
        - category
        Category name.

        Returns a string 


        All functions with prefix 'make_lex' return a string that will be part of a longer
        string (lexicon string) that will be used as an input for a NLTK function that generates 
        the lexicon itself.

        The current function generates part of the lexicon string for specified category 'category' 
        for rules that are not complex and may be generated 
        automatically. For example, for category 'CALLSIGN' these rules will be generated:

        ```
        callsign1 => CALLSIGN {_CALLSIGN_(callsign1)}
        callsign2 => CALLSIGN {_CALLSIGN_(callsign2)}
        ...
        ```
        Here for each placeholder (callsign1, callsign2, ...) up to the maximum number of 
        placeholders
        assigned to the category CALLSIGN we define a rule with syntactic and semantic parts. Here 
        category 'CALLSIGN' defines the syntactic part while '_CALLSIGN_(callsignX)' its 
        semantic part.

        """
        res = ""
        for placeholder in dData['category_placeholder'][category]:
            res = res + str(placeholder) + " => "+category.upper()+" {_"+category.upper()+'_('+str(placeholder)+")}\n"
            
        return(res)
    
    
    def make_lex_complex(dLexComplex):

        """
        Argument:
        - dLexComplex
        A dictionary with information about 'complex' rules.

        Returns a string.

        This function generates a part of lexicon string for all 'complex' rules from *dLexComplex*.

        For example
        ```
        aircraft1 => CALLSIGN/CALLSIGN {\\x._CALLSIGN_(_AIRCRAFT_(aircraft1),x)}
        aircraft2 => CALLSIGN/CALLSIGN {\\x._CALLSIGN_(_AIRCRAFT_(aircraft2),x)}
        ...
        ```
        Here for each placeholder (aircraft1, aircraft2, ...) up to the maximum number of 
        placeholders
        assigned to the category 'AIRCRAFT' we define a rule with syntactic and semantic parts. Here 
        category 'CALLSIGN/CALLSIGN' defines the syntactic part while function 
        ```
        \\x._CALLSIGN_(_AIRCRAFT_(aircraft1),x)
        ``` 
        its semantic part.

        """
    
        res = ""
        for placeholder in dLexComplex:
            a_ccg = dLexComplex[placeholder]
            #category name may be extracted from placeholder name
            category = placeholder.replace('1','').upper()
            # jst replace 1st placeholder from a rule from dLexComplex with all other placeholder related 
            # to related category
            for lex in a_ccg:
                for placeholder_new in dData['category_placeholder'][category]:
                    res = res + placeholder_new + " => "+lex.replace(placeholder,placeholder_new)+"\n"
            
        return(res)

    
    def make_lex_preposition():
        """
        Returns a string.

        Lets we have this phrase in an ATC command: '... the localizer ...'. Here 'localizer'
        belongs to the category 'NAVAID'. We want the same to be true for the phrase 'the localizer' 
        where 'the' is a preposition. 
        
        Also if
        a word/phrase is unknown (doesn't belong to any category in *regex.txt* or the list of 
        prepositions) then we assign it automatically to the lexical 
        category *NP*. So for example, word 'abracadabra' belongs to NP. We want the same 
        to be true for phrase
        'the abaracadabra'.

        So for 'the' we want to have automatically generated rules:

        ```
        the => NAVAID/NAVAID {\\x._the_(x)}
        ```
        for category *NAVAID*, and

        ```
        the => NP/NP {\\x._the_(x)}
        ```
        for all unknown words/phrases.

        """


        res = ""
        for category in dData['category_frequency']:
            for preposition in dData['prepositions']:
                res = res + preposition + " => "+category+"/"+category+" {\\x._"+preposition+r"_(x)}"+"\n"
        for preposition in dData['prepositions']:
            res = res + preposition + " => NP/NP {\\x._"+preposition+r"_(x)}"+"\n"

            
            
        return(res)
    
    def lex_words(lexicon, dData):
        '''
        Arguments:
        - lexicon
        The lexicon for the ATC commands parsing.
        - dData
        We update dData with information about all words that occur in the lexicon.

        This function is used when the lexicon' is generated. It extract all words from it. 
        Results are stored in *dData*. We need this information to extract unknow phrases from a 
        command we want to parse.
        '''
        dLexWords = {}

        for x in str(lexicon).split('\n'):
            word = x.split('=>')
            dLexWords[word[0].strip()] = 1
        
        dData['lex_words'] = dLexWords

    
    read_regex(regex_file, dData)

    read_prepositions(prepositions_file, dData)

    read_category_filters(category_filters_file, dData)

    
    """
    ## Lexicon generation ##

    To generate a lexicon using NLTK we need to prepare a string (*lexicon string*) with 
    information about all rules we want to include in the lexicon. 

    # lex_categories #

    But it should start with list of all categories. This list starts with categories common to 
    any application that uses NLTK CCG parser: 

    """
    
    lex_categories = ":- S,NP,N,ADJ,VP,PP,P,JJ,JJR,DT,PPN,NNP\n"

    """
    Then we need to add all categories that we defined in 'regex.txt':
    """

    for category in sorted(dData['category_frequency']):
        lex_categories = lex_categories.strip('\n')+','+category.upper()
    lex_categories = lex_categories+'\n'
    

    """
    ## lex_common ##

    These are a few special rules that we want to add to the lexicon. 
    
    Rules for string '_context_' are used in a trick that we use to guarantee that 
    the parsing process will stop. 

    Please note that in the case of long commands we can't guarantee that the parsing process 
    will stop with a result. It may be just an empty set of results.

    To avoid this, we do some modifications of the original sentence (including its splitting) to
    get something useful in all cases.

    Rules for word 'no' are the basis to introduce negation to the system.
    """

    lex_common = '''

    _context_ => (S/S)/NP {\\x y._context_(x,y)}
    _context_ => (S/NP)/S {\\y x._context_(x,y)}
    _context_ => S/NP {\\z._context_(z)}
    
    no => S/NP {\\z._no_(z)}
    no => S/S {\\z._no_(z)}

    '''

    
    for category in sorted(dData['category_frequency']):
        
        lex_common = (lex_common+'\n'+
            
            '_context_ => (S/S)/'+category.upper()+' {\\x y._context_(x,y)}\n'+
            '_context_ => (S/'+category.upper()+')/S {\\y x._context_(x,y)}\n'+
            '_context_ => S/'+category.upper()+' {\\z._context_(z)}\n'
            )
    

        lex_common = (lex_common+'\n'+
            'and => '+category.upper()+'/'+category.upper()+' {\\x._AND_(x)})\n'
            )
        
    
    """
    # lex_all_category #

    Update lexicon with simple rules for each placeholder
    """

    lex_all_category = ''
    for category in dData['category_frequency']:
        lex_all_category = lex_all_category + make_lex_all_category(category)

    """
    # lex_complex #

    Read lexicon complex file with and witout filters.
    
    # no filter #
    
    """
    dLexComplex = {}
    with_filter = False
    read_lexicon_complex(lex_complex_file, dLexComplex, with_filter)
    lex_complex_no_filter = make_lex_complex(dLexComplex)
    
    #with filter
    dLexComplex = {}
    with_filter = True
    read_lexicon_complex(lex_complex_file, dLexComplex, with_filter)
    lex_complex_with_filter = make_lex_complex(dLexComplex)
    
    """
    # lex_prepositions #
    """
    
    lex_prepositions = make_lex_preposition()

    
    """
    # lex_last_part #

    We use these rules to represent all words/phases not recognised by patterns in *regex.txt* and
    not included in prepositions list with special 'CONTEXT' category. 
    
    For this category we use 12 special placeholders X1,...,X12   
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

    """
    # Finally #

    Now we can generate lexicon using NLTK 
    ```
    lexicon.fromstring() 
    ```
    function where the its single
    argument (lexicon string) is the concatenation of strings of rules generated above.

    Here we generate two lexicons - without filter and with filter. Function *lex_words()* is
    used only for lexicon with filter.
    """

    lex_no_filter = lexicon.fromstring(lex_categories + 
                                lex_common + 
                                lex_all_category +
                                lex_complex_no_filter +
                                lex_prepositions +
                                lex_last_part, True)
    
    lex_words(lex_no_filter, dData)

    lex_with_filter = lexicon.fromstring(lex_categories + 
                                lex_common + 
                                lex_all_category +
                                lex_complex_with_filter +
                                lex_prepositions +
                                lex_last_part, True)
    
    
    """
    ## CCG parsers ##

    Now we can generate two NLTK CCG parsers for lexicon without or with filters.

    The parser where we use lexicon without filter - *command_parser*, may be used for commands
    represented in normal textual form. 

    The parser with lexicon with filter - *LF_parser*, will be used during 2nd, 3rd,... steps
    of the parsing process. Here input is a logical form returned by the previous step.
    """

    command_parser = chart.CCGChartParser(lex_no_filter, chart.ApplicationRuleSet + chart.CompositionRuleSet)
    LF_parser = chart.CCGChartParser(lex_with_filter, chart.ApplicationRuleSet + chart.CompositionRuleSet)

    dData['command_parser'] = command_parser
    dData['LF_parser'] = LF_parser



def parsing(command, number_of_steps, dData):
    """
    ## Parsing ##

    Arguments:
    - *command*
    Original ATC command in textual form. Please note that we ignore punctuation.
    - *number_of_steps*
    The first step (step index 0) takes the original textual command as input and produces a 
    logical form that represents semantics of the command. Depending on the command complexity, 
    it may be possible to make one or more additional steps where logical form returned by 
    previous step is parsed to get new compressed logical form if this is possible. 
    The value of the parameter is the maximum number of steps that will be produced. 
    The real number may be smaller if logical forms that are produced 
    in two sequential steps are identical.
    - dData
    The dictionary generated by *make_lexicon()* function. It contains all data that we need to
    parse the command in any number of steps. 

    
    Returns logical form (string) that represents semantics of the command
    """

    def command_normalization (command):
        """
        Command normalization including reduction of punctuation and replacement of some
        contracted expressions by their complete forms. Returns normalized command.
        
        """
        pattern = r"\b(re\-)[a-z]+"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(command)
        for match in iterator:
            if match:
                command = re.sub(match.group(1),"re", command, count=0)

        pattern = r"\b[a-z]+(\-)[a-z]+"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(command)
        for match in iterator:
            if match:
                command = re.sub(match.group(1)," ", command, count=0)
                

        pattern = r"\b\d+(\-)\d\b"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(command)
        for match in iterator:
            if match:
                command = re.sub(match.group(1),"", command, count=0)

        
        command = command.replace("; "," ").replace(": "," ").replace(", "," ").replace(". "," ").replace("? "," ").replace('—',' ').replace("-"," ").replace("=","-").replace("’","'").replace("o'","o")
        command = command.replace(",","")
        command = command.replace("I'd","i would").replace("it's","it is").replace("what's","what is").replace("that's","that is").replace("'s","").replace("'ve"," have").replace("'ll"," will").replace("'re"," are").replace(" a "," ")
        command = command.replace(r"\s+"," ").replace("+","")
        command = command.strip('.,?!\n”"')

        return command
    
    def parse_command(parser, command, dData, step):
        """
        Main function to parse a command.
        Arguments:
        - parser
        May be the parser with lexicon without filter to use for textual command or 
        the parser with lexicon with filter to use for logical forms,
        - command
        Textual command or logical form,
        - dData 
        Dictionary produced by *make_lexicon()* function,
        - step
        Index of the step (0 for first step for textual command)

        
        Returns a string - logical form
        """

        def clean_LF(LF):
            """
            In some cases logical form that we generate in the parsing process
            may be too complicated and we may have the possibility to simplify it.

            Returns string - cleaned logical form.
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
        
        def text2placeholders(command, dData, dReplacement):
            """
            Arguments:
            - command
            Textual command after normalization,
            - dData 
            Dictionary generated by *make_lexicon()* function,
            - dReplacement
            Output dictionary with mapping of placeholders to phrases from the command

            Returns a string - a sequence of placeholders (and, possibly, unrecognized words/phrases).

            This function is used on the step with index 0 to convert the original textual command 
            to a string of placeholders. Please note that if the command contains unrecognized
            words/phrases (unrecognised by any regex), we leave it as it is.
            """
            new_command = command
            dCategoryMaxPlaceholderNumber = {}
            
            """
            Here we extract words/phrases from command relevant to a regex from *regex.txt*. 
            We use a greedy approach - use the most complex applicable regex first. 
            The relevant word/phrase is replaced
            by the placeholder -- category name expanded with an integer number. 

            The same word/phrase may occur in the command more than once. To have 
            one-to-one correspondence between placeholders and related words/phrases in 
            dReplacement we use a trick -- because keys in dReplacement are just extracted 
            words/phrases we guarantee uniqueness
            surrounding the word/phrase with unique number of open and close symbols '<' and '>'.
            """

            count = 0
            new_command_ok = True
            while new_command_ok:
                new_command_ok = False
                for pattern in sorted(dData['regex_complexity'], key=dData['regex_complexity'].get, reverse=True):
                    if pattern == '':
                        continue
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(new_command)
                    
                    for match in iterator:
                        if match:
                            count += 1
                            category = dData['regex_category'][pattern]
                            
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

        def replace_unknown_phrases(command, dData, dReplacement):
            """
            Arguments:
            - command
            A string returned by *text2placeholders()* function,
            - dData
            Dictionary generated by *make_lexicon()* fuction, 
            - dReplacement
            Output dictionary with mapping of special X1,...,X12 placeholders to 
            unrecognized phrases from the command

            Returns a string - a sequence of placeholders (possibly with some normal words -
            prepositions).


            Given a string of placeholders (command), it is possible that it may still contain 
            normal words/phrases. It is possible if this word/phrase is
            outside the lexicon (and list of prepositions) -- they are not covered by any regex. 
            We call such words/phrases unknown,
            and we want to replace them with special placeholders - X1, X2, ...

            This function is just doing this, returning a string of placeholders where unknown 
            phrases are replaced with special placeholders. 
            
            Please note that it still may contain normal words 
            but only some prepositions. 
            
            Output dictionary dReplacement maps unknown phrases into special
            placeholders X1, X2, ...

            """

            """
            clean command (with placeholders -- now we can do this)
            """
            command = command.replace(':','').replace(';','').replace(',','').replace('.','').replace('+','').lower()
            
            """
            command where words from the lexicon are replaced with 'Y'
            """
            command_no_lex = command

            for word in sorted(dData['lex_words']):
                if word == '':
                    continue
                pattern = word+r"\b"
                if pattern[0] not in {'-'}:
                    pattern = r"\b"+pattern

                p = re.compile(pattern, re.I)
                iterator = p.finditer(command)
                for match in iterator:
                    if match:
                        
                        if (match.group()).isalpha() and match.group() not in set(dData['prepositions']):
                            continue

                        to_replace = match.group()+r"\b"
                        if to_replace[0] not in {'-','+'}:
                            to_replace = r"\b"+to_replace

                        to_replace = to_replace.strip('+')


                        command_no_lex = re.sub(to_replace,r"Y", command_no_lex, count=1)

            """          
            replace unknow phrases with X1, X2,...   
            """       
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

        

        def LF2placeholders(LF, dReplacement):

            """
            Arguments:
            - LF
            Logical form (string) - results of the parsing on the previous step,
            - dReplacement
            Replacement of the new placeholders by related functions from the LF.

            Returns a string - a new sequence of placeholders.

            This function is used to generate placeholders on all steps except step index 0. 
            The difference is that here, instead of the original textual command, we have a logical form 
            (LF). That is the result of semantic parsing on the previous step.

            This is an example of such LF after step index 0 for the command
            "*Southwest 578 cleared to Atlanta via radar vectors then ...*:
            

            ```
            _CALLSIGN_(_AIRCRAFT_(*Southwest*),_INTNUMBER_(*578*)); _CLEARED_(_CLEARED_(*cleared*),_TO_(*to*),_PLACE_(*Atlanta*)); _VIA_(*via*); _RADAR_(*radar vectors*); _THEN_(_THEN_(*then*),_ROUTE_(_ROUTE_(*V222*),_TO_(*to*),_FIX_(*CRG*))); _THEN_(_THEN_(*then*),_DIRECTION_(*direct*)); _ALTITUDECHANGE_(_ALTITUDECHANGE_(*Climb and maintain*),_INTNUMBER_(*5000*)); _EXPECT_(_EXPECT_(*expect*),_INTNUMBER_(*35000*)); _TIME_(_WORDNUMBER_(*ten*),_TIMEMINSEC_(*minutes*)); _AFTER_(_AFTER_(*after*),_DEPARTURE_(*departure*)); _DEPARTURE_(_DEPARTURE_(*Departure*),_FREQUENCY_(_FREQUENCY_(*frequency*),_REALNUMBER_(*124.85*))); _SQUAWK_(_SQUAWK_(*squawk*),_INTNUMBER_(*5263*));
            ```
            In this case, we can split the LF by ';' into a sequence of functions: CALLSIGN, CLEARED, ...
            We use names of these functions (category names) to generate placeholders: callsign1, 
            cleared1, ...
            
            As a replacement for placeholder callsign1 we use the related function 
            from LF - _CALLSIGN_(_AIRCRAFT_(*Southwest*),_INTNUMBER_(*578*)).

            
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

        
        def parse_segment(parser, segment, maxExpansions, dReplacement_1, dReplacement_2):
            """
            Arguments:
            -parser
            The same as in *parsing()* function
            - segment
            Part of the command that may be parsed successfully,
            - maxExpansions
            Maximum number of expansion of the segment with special term '_context_' -
            a trick to increase the probability that the segment will be parsed successfully,
            - dReplacement_1
            Dictionary of placeholder replacements to replace placeholders  with the correct
            words/phrases from the segment,
            - dReplacement_2
            Dictionary of special placeholder (X1, X2,...) replacements to replace 
            placeholders with the correct unknown words/phrases from the segment.

            Returns logical form (a string) -- the result of parsing the segment.

            This function returns a logical form (LF) given a parser and a segment of 
            a command we want to parse. Please note that if a command is long and we can't 
            parse it using CCG, then we try to split it into segments that can be parsed, still 
            being semantically complete.

            The problem is that the parser may return an empty result even for a segment. 
            This depends on the lexicon (used in parser generation) and the segment itself. 
            

            To reduce the probability of such event, we use a trick 
            -- expanding original segment with zero, one or more (up to maxExpansions) copies of 
            special term '_context_' that we add in the very beginning of the segment. 
            
            We start with zero copies of the term and stop if the parsing is successful or
            the number of copies achieved its maximum.

            The LF that we get as a result of the parsing still contains placeholders instead of 
            real words/phrases from the segment. We use dictionaris *dReplacement_1* and 
            *dReplacement_2* that should store the correct replacements of these placeholders.
            """


            nExpansions = 0
            nParses = 0
            parses = []

        
            segment_expanded = segment
            """
            The parsing is successful if 
            ```
            nParses > 0
            ```
            """
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


        LF_final = ''

        dReplacement_1 = {}
        dReplacement_2 = {}
        command_new = ''

        if step == 0:
            new_command_1 = text2placeholders(command, dData, dReplacement_1)
            new_command_2 = replace_unknown_phrases(new_command_1, dData, dReplacement_2)
            command_new = new_command_2
            
            pattern = r"\b(x)\d+\b"
            p = re.compile(pattern, re.I)
            iterator = p.finditer(command_new)
            for match in iterator:
                if match:
                    command_new = re.sub(match.group(1),"X", command_new, count=1)
        else:
            command_new = LF2placeholders(command, dReplacement_1)
            
        

        # parse command with expansion -------------------------

        maxExpansion = 1
        
        LF_replacement = parse_segment(parser, command_new, maxExpansion, dReplacement_1, dReplacement_2)
        if LF_replacement != '':

            """
            Clean function _context_(...) by its argument if it is another function
            """
            pattern = r"\b_context_\(_(.+)\)"
            p = re.compile(pattern, re.I)
            iterator = p.finditer(LF_replacement)
            for match in iterator:
                if match:            
                    LF_replacement = LF_replacement.replace(str(match.group(0)), '_'+str(match.group(1)))
            
            if step > 0:
                LF_replacement = clean_LF(LF_replacement)
                
            
            LF_final = LF_final +LF_replacement+'; '
        else:
            """ 
            we need to split the sentence into segments
            """
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

                        if step > 0:
                            LF_replacement = clean_LF(LF_replacement)
                            
                        LF_final = LF_final +LF_replacement+'; '
                        command_new = ' '.join(command_new_words[j+1:len(command_new_words)+1])   
                        break
                    
                    if LF_replacement == '' and j == 0:
                        command_new = ''

        if step > 0:
            LF_final = LF_final.replace('STOP_(','_(')            
            LF_final = LF_final.replace('\n*','')            
                
                            
        return LF_final

    command = command_normalization(command)
    command_parser = dData['command_parser']
    LF_parser = dData['LF_parser']

    LF_old = ''
    for i in range(number_of_steps):
        if i == 0:
            LF = parse_command(command_parser, command, dData, i)
            if LF == LF_old:
                break
            else:
                LF_old = LF
        else:
            LF = parse_command(LF_parser, LF, dData, i)
            if LF == LF_old:
                break
            else:
                LF_old = LF

    return LF


def parsing_debug(command, number_of_steps, dData, dPlaceholders):
    """
    ## Parsing that returns placeholders to get more information about parsing ##

    Use this instead of parsing() if you need more information to update files from data folder

    Arguments:
    - *command*
    Original ATC command in textual form. Please note that we ignore punctuation.
    - *number_of_steps*
    The first step (step index 0) takes the original textual command as input and produces a 
    logical form that represents semantics of the command. Depending on the command complexity, 
    it may be possible to make one or more additional steps where logical form returned by 
    previous step is parsed to get new compressed logical form if this is possible. 
    The value of the parameter is the maximum number of steps that will be produced. 
    The real number may be smaller if logical forms that are produced 
    in two sequential steps are identical.
    - dData
    The dictionary generated by *make_lexicon()* function. It contains all data that we need to
    parse the command in any number of steps. 
    - dPlaceholders 
    Additional output data that may help to fix problems with parsing. Store
    placeholdes for each parsing step
    
    Returns logical form (string) that represents semantics of the command
    """

    def command_normalization (command):
        """
        Command normalization including reduction of punctuation and replacement of some
        contracted expressions by their complete forms. Returns normalized command.
        
        """
        pattern = r"\b(re\-)[a-z]+"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(command)
        for match in iterator:
            if match:
                command = re.sub(match.group(1),"re", command, count=0)

        pattern = r"\b[a-z](\-)[a-z]+"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(command)
        for match in iterator:
            if match:
                command = re.sub(match.group(1),"=", command, count=0)


        pattern = r"\b\d+(\-)\d\b"
        p = re.compile(pattern, re.I)
        iterator = p.finditer(command)
        for match in iterator:
            if match:
                command = re.sub(match.group(1),"", command, count=0)

        
        command = command.replace("; "," ").replace(": "," ").replace(", "," ").replace(". "," ").replace("? "," ").replace('—',' ').replace("-"," ").replace("=","-").replace("’","'").replace("o'","o")
        command = command.replace(",","")
        command = command.replace("I'd","i would").replace("it's","it is").replace("what's","what is").replace("that's","that is").replace("'s","").replace("'ve"," have").replace("'ll"," will").replace("'re"," are").replace(" a "," ")
        command = command.replace(r"\s+"," ").replace("+","")
        command = command.strip('.,?!\n”"')

        print('???'+command)

        return command
    
    def parse_command(parser, command, dData, step, dPlaceholders):
        """
        Main function to parse a command.
        Arguments:
        - parser
        May be the parser with lexicon without filter to use for textual command or 
        the parser with lexicon with filter to use for logical forms,
        - command
        Textual command or logical form,
        - dData 
        Dictionary produced by *make_lexicon()* function,
        - step
        Index of the step (0 for first step for textual command)
        - dPlaceholders
        Additional output data that may help to fix problems with parsing. Store
        placeholdes for each parsing step
        
        Returns a string - logical form
        """

        def clean_LF(LF):
            """
            In some cases logical form that we generate in the parsing process
            may be too complicated and we may have the possibility to simplify it.

            Returns string - cleaned logical form.
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
        
        def text2placeholders(command, dData, dReplacement):
            """
            Arguments:
            - command
            Textual command after normalization,
            - dData 
            Dictionary generated by *make_lexicon()* function,
            - dReplacement
            Output dictionary with mapping of placeholders to phrases from the command

            Returns a string - a sequence of placeholders (and, possibly, unrecognized words/phrases).

            This function is used on the step with index 0 to convert the original textual command 
            to a string of placeholders. Please note that if the command contains unrecognized
            words/phrases (unrecognised by any regex), we leave it as it is.
            """
            new_command = command
            dCategoryMaxPlaceholderNumber = {}
            
            """
            Here we extract words/phrases from command relevant to a regex from *regex.txt*. 
            We use a greedy approach - use the most complex applicable regex first. 
            The relevant word/phrase is replaced
            by the placeholder -- category name expanded with an integer number. 

            The same word/phrase may occur in the command more than once. To have 
            one-to-one correspondence between placeholders and related words/phrases in 
            dReplacement we use a trick -- because keys in dReplacement are just extracted 
            words/phrases we guarantee uniqueness
            surrounding the word/phrase with unique number of open and close symbols '<' and '>'.
            """

            count = 0
            new_command_ok = True
            while new_command_ok:
                new_command_ok = False
                for pattern in sorted(dData['regex_complexity'], key=dData['regex_complexity'].get, reverse=True):
                    if pattern == '':
                        continue
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(new_command)
                    
                    for match in iterator:
                        if match:
                            count += 1
                            category = dData['regex_category'][pattern]
                            
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

        def replace_unknown_phrases(command, dData, dReplacement):
            """
            Arguments:
            - command
            A string returned by *text2placeholders()* function,
            - dData
            Dictionary generated by *make_lexicon()* fuction, 
            - dReplacement
            Output dictionary with mapping of special X1,...,X12 placeholders to 
            unrecognized phrases from the command

            Returns a string - a sequence of placeholders (possibly with some normal words -
            prepositions).


            Given a string of placeholders (command), it is possible that it may still contain 
            normal words/phrases. It is possible if this word/phrase is
            outside the lexicon (and list of prepositions) -- they are not covered by any regex. 
            We call such words/phrases unknown,
            and we want to replace them with special placeholders - X1, X2, ...

            This function is just doing this, returning a string of placeholders where unknown 
            phrases are replaced with special placeholders. 
            
            Please note that it still may contain normal words 
            but only some prepositions. 
            
            Output dictionary dReplacement maps unknown phrases into special
            placeholders X1, X2, ...

            """

            """
            clean command (with placeholders -- now we can do this)
            """
            command = command.replace(':','').replace(';','').replace(',','').replace('.','').replace('+','').lower()
            
            """
            command where words from the lexicon are replaced with 'Y'
            """
            command_no_lex = command

            for word in sorted(dData['lex_words']):
                if word == '':
                    continue
                pattern = word+r"\b"
                if pattern[0] not in {'-'}:
                    pattern = r"\b"+pattern

                p = re.compile(pattern, re.I)
                iterator = p.finditer(command)
                for match in iterator:
                    if match:
                        
                        if (match.group()).isalpha() and match.group() not in set(dData['prepositions']):
                            continue

                        to_replace = match.group()+r"\b"
                        if to_replace[0] not in {'-','+'}:
                            to_replace = r"\b"+to_replace

                        to_replace = to_replace.strip('+')


                        command_no_lex = re.sub(to_replace,r"Y", command_no_lex, count=1)

            """          
            replace unknow phrases with X1, X2,...   
            """       
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

        

        def LF2placeholders(LF, dReplacement):

            """
            Arguments:
            - LF
            Logical form (string) - results of the parsing on the previous step,
            - dReplacement
            Replacement of the new placeholders by related functions from the LF.

            Returns a string - a new sequence of placeholders.

            This function is used to generate placeholders on all steps except step index 0. 
            The difference is that here, instead of the original textual command, we have a logical form 
            (LF). That is the result of semantic parsing on the previous step.

            This is an example of such LF after step index 0 for the command
            "*Southwest 578 cleared to Atlanta via radar vectors then ...*:
            

            ```
            _CALLSIGN_(_AIRCRAFT_(*Southwest*),_INTNUMBER_(*578*)); _CLEARED_(_CLEARED_(*cleared*),_TO_(*to*),_PLACE_(*Atlanta*)); _VIA_(*via*); _RADAR_(*radar vectors*); _THEN_(_THEN_(*then*),_ROUTE_(_ROUTE_(*V222*),_TO_(*to*),_FIX_(*CRG*))); _THEN_(_THEN_(*then*),_DIRECTION_(*direct*)); _ALTITUDECHANGE_(_ALTITUDECHANGE_(*Climb and maintain*),_INTNUMBER_(*5000*)); _EXPECT_(_EXPECT_(*expect*),_INTNUMBER_(*35000*)); _TIME_(_WORDNUMBER_(*ten*),_TIMEMINSEC_(*minutes*)); _AFTER_(_AFTER_(*after*),_DEPARTURE_(*departure*)); _DEPARTURE_(_DEPARTURE_(*Departure*),_FREQUENCY_(_FREQUENCY_(*frequency*),_REALNUMBER_(*124.85*))); _SQUAWK_(_SQUAWK_(*squawk*),_INTNUMBER_(*5263*));
            ```
            In this case, we can split the LF by ';' into a sequence of functions: CALLSIGN, CLEARED, ...
            We use names of these functions (category names) to generate placeholders: callsign1, 
            cleared1, ...
            
            As a replacement for placeholder callsign1 we use the related function 
            from LF - _CALLSIGN_(_AIRCRAFT_(*Southwest*),_INTNUMBER_(*578*)).

            
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

        
        def parse_segment(parser, segment, maxExpansions, dReplacement_1, dReplacement_2):
            """
            Arguments:
            -parser
            The same as in *parsing()* function
            - segment
            Part of the command that may be parsed successfully,
            - maxExpansions
            Maximum number of expansion of the segment with special term '_context_' -
            a trick to increase the probability that the segment will be parsed successfully,
            - dReplacement_1
            Dictionary of placeholder replacements to replace placeholders  with the correct
            words/phrases from the segment,
            - dReplacement_2
            Dictionary of special placeholder (X1, X2,...) replacements to replace 
            placeholders with the correct unknown words/phrases from the segment.

            Returns logical form (a string) -- the result of parsing the segment.

            This function returns a logical form (LF) given a parser and a segment of 
            a command we want to parse. Please note that if a command is long and we can't 
            parse it using CCG, then we try to split it into segments that can be parsed, still 
            being semantically complete.

            The problem is that the parser may return an empty result even for a segment. 
            This depends on the lexicon (used in parser generation) and the segment itself. 
            

            To reduce the probability of such event, we use a trick 
            -- expanding original segment with zero, one or more (up to maxExpansions) copies of 
            special term '_context_' that we add in the very beginning of the segment. 
            
            We start with zero copies of the term and stop if the parsing is successful or
            the number of copies achieved its maximum.

            The LF that we get as a result of the parsing still contains placeholders instead of 
            real words/phrases from the segment. We use dictionaris *dReplacement_1* and 
            *dReplacement_2* that should store the correct replacements of these placeholders.
            """


            nExpansions = 0
            nParses = 0
            parses = []

        
            segment_expanded = segment
            """
            The parsing is successful if 
            ```
            nParses > 0
            ```
            """
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


        LF_final = ''

        dReplacement_1 = {}
        dReplacement_2 = {}
        command_new = ''

        if step == 0:
            new_command_1 = text2placeholders(command, dData, dReplacement_1)
            new_command_2 = replace_unknown_phrases(new_command_1, dData, dReplacement_2)
            command_new = new_command_2
            
            pattern = r"\b(x)\d+\b"
            p = re.compile(pattern, re.I)
            iterator = p.finditer(command_new)
            for match in iterator:
                if match:
                    command_new = re.sub(match.group(1),"X", command_new, count=1)
        else:
            command_new = LF2placeholders(command, dReplacement_1)
        
        dPlaceholders[step] = command_new
            
        

        # parse command with expansion -------------------------

        maxExpansion = 1
        
        LF_replacement = parse_segment(parser, command_new, maxExpansion, dReplacement_1, dReplacement_2)
        if LF_replacement != '':

            """
            Clean function _context_(...) by its argument if it is another function
            """
            pattern = r"\b_context_\(_(.+)\)"
            p = re.compile(pattern, re.I)
            iterator = p.finditer(LF_replacement)
            for match in iterator:
                if match:            
                    LF_replacement = LF_replacement.replace(str(match.group(0)), '_'+str(match.group(1)))
            
            if step > 0:
                LF_replacement = clean_LF(LF_replacement)
                
            
            LF_final = LF_final +LF_replacement+'; '
        else:
            """ 
            we need to split the sentence into segments
            """
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

                        if step > 0:
                            LF_replacement = clean_LF(LF_replacement)
                            
                        LF_final = LF_final +LF_replacement+'; '
                        command_new = ' '.join(command_new_words[j+1:len(command_new_words)+1])   
                        break
                    
                    if LF_replacement == '' and j == 0:
                        command_new = ''

        if step > 0:
            LF_final = LF_final.replace('STOP_(','_(')            
            LF_final = LF_final.replace('\n*','')            
                
                            
        return LF_final

    command = command_normalization(command)
    command_parser = dData['command_parser']
    LF_parser = dData['LF_parser']

    LF_old = ''
    for i in range(number_of_steps):
        if i == 0:
            LF = parse_command(command_parser, command, dData, i, dPlaceholders)
            if LF == LF_old:
                break
            else:
                LF_old = LF
        else:
            LF = parse_command(LF_parser, LF, dData, i, dPlaceholders)
            if LF == LF_old:
                break
            else:
                LF_old = LF

    return LF


def logicalForm2JSON(LF):
    """
    If you prefer read semantics of a command using JSON format, them you can use this function.

    Arguments:
    - LF
    Parsing results in logical form (string)

    Returns JSON string.
    """
    
    def clean_JSON(sJSON):
        """
        Clean JSON string.
        """
        """
        Delete '{' and '}' around '"..."'
        """
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

        """
        Delete ',' and '\s' before '}'
        """
        while True:
            sJSON_new = sJSON 
            pattern = r"[\,\s]+\}" 
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
        
        """
        Delete simple duplicated functions. Replace
        ``` 
        "xyz":{"xyz":{...}}
        ```
        with
        ```
        "xyz":{...}
        ```
        """
        while True:
            sJSON_new = sJSON

            pattern = r"(\"[a-z]+\"\:\{)(\1[\"\w\d\s\_\:\,]+\})\}"
            p = re.compile(pattern, re.I)
            iterator = p.finditer(sJSON)
            for match in iterator:
                if match:
                
                    to_replace = str(match.group())
                    replace_by = str(match.group(2))
                    
                    sJSON_new = re.sub(to_replace,replace_by, sJSON_new, count=1)

            if sJSON_new == sJSON:
                break
            else:
                sJSON = sJSON_new


        """
        replace 
        ```
        the":{"xyz":{...}}
        ```
        with
        ```
        the_xyz":{...}
        ```
        where instead of 'the' may be any word from
        ```
        ['the','have','your','are','over','be','an']
        ```
        """

        for word in ['the','have','your',
                    'are','over','be',
                    'an']:
            for brackets in ['0','1','2','3']:
                while True:
                    
                    pattern = r"\""+rf"{re.escape(word)}"+r"\"\:\{([\"\w\d\s\_\:\,\'\{\}]+?\}{"+rf"{re.escape(brackets)}"+"})\}"
                    p = re.compile(pattern, re.I)
                    iterator = p.finditer(sJSON)
                    for match in iterator:
                        if match:
                        
                            to_replace = str(match.group())
                            replace_by = str(match.group(1))
                            
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
                                replace_by = '\"'+word+' '+replace_by[1:]
                                sJSON_new = re.sub(to_replace,replace_by, sJSON, count=0)

                    if sJSON_new != sJSON:
                        sJSON = sJSON_new
                        
                    break
    
        return sJSON
    

    def make_unique_keys(sJSON):
        """
        All keys in JSON should be unique. In our case key is a category, and we may have more than
        one identical category in the parsing results. To get unique, we add an integer index to each category.
        """

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
                if to_replace_key not in dKeys:
                    dKeys[to_replace_key] = 0
                id = int(dKeys[to_replace_key]) + 1
                dKeys[to_replace_key] = id
                replace_by = '\"'+to_replace.strip(':\"')+'_'+str(id)+'\":'
                
            sJSON = re.sub(to_replace,replace_by, sJSON, count=1)

        return sJSON


    sJSON = '{'+LF.strip('\s\t\n').replace(';',',').replace('_(','\":{').replace('_','\"').replace(')','}').replace('*','\"')+'}'
    sJSON = clean_JSON(sJSON)
    sJSON = make_unique_keys(sJSON)

    return sJSON
    

