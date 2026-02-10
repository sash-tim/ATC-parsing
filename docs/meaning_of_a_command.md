# Meaning of a command

## Contents
- [What is the meaning?](#what-is-the-meaning)

## What is the meaning?

In his "Philosophical Investigations", Ludwig Wittgenstein said

> "The meaning of a word is its use in the language"
> - <cite> Ludwig Wittgenstein </cite> 

Here by language Wittgenstein means not the whole language but context-dependent *language game*. In our case, this is Air Traffic Control (ATC) communications.

We try to represent the meaning of an ATC command using the CCG parser and the specially developed ATC-related lexicon.

This is a simple example:

```
COMMAND: Speedbird 123 climb flight level three four zero.

PARSE (JSON):
{
  "CALLSIGN": {
    "AIRCRAFT": "Speedbird",
    "INTNUMBER": "123"
  },
  "ALTITUDECHANGE": {
    "ALTITUDECHANGE": "climb",
    "FLEVEL": {
      "FLEVEL": "flight level",
      "FLEVELVALUE": "three four zero"
    }
  }
}

```
This JSON contains:
1) All words from original command in the natural order

2) Categories: 

>- CALLSIGN
>- AIRCRAFT
>- INTNUMBER
>- ALTITUDECHANGE
>- FLEVEL
>- FLEVELVALUE

3) Functions:
>- CALLSIGN ( AIRCRAFT, INTNUMBER )
>- ALTITUDECHANGE ( ALTITUDECHANGE, FLEVEL )
>- FLEVEL ( FLEVEL, FLEVELVALUE)

Both categories and functions are defined in the lexicon that controls the parsing process. We believe that this combination of the command words, categories and structures represented with nested functions may help understand the command meaning.

Other sections of the document will discuss some more specific interesting cases of the ATC commands.