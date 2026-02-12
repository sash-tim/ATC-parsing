# Meaning of a command

## Contents
- [What is the meaning?](#what-is-the-meaning)
- [Traffic in sight](#traffic-in-sight)
- [Scope of the HOLD instruction](#scope-of-the-hold-instruction)

## What is the meaning?

In his "Philosophical Investigations", Ludwig Wittgenstein said

> "The meaning of a word is its use in the language"
> - <cite> Ludwig Wittgenstein </cite> 

Here by language Wittgenstein means not the whole language but context-dependent *language game*. In our case, this is Air Traffic Control (ATC) communications.

We try to represent the meaning of an ATC command using the CCG parser and the specially developed ATC-related lexicon.

This is a simple example:

```
COMMAND: Speedbird 123 climb flight level three four zero.

PARSE (simplified JSON):
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

## Traffic in sight

In this ATC command, the controller warns the pilot about another aircraft (traffic) the pilot should be worried about, and asks the pilot to report when the traffic will be in sight.


```
COMMAND: SkyWest 3124 traffic twelve o’clock three miles opposite direction altitude indicates nine thousand Advise when you have the traffic in sight

```

The command contains information about the traffic that may help the pilot in looking for the traffic:

>- Direction to the traffic relative to the pilot position: *twelve o’clock*
>- Distance to the traffic:  *three miles*
>- Direction of the traffic flow:  *opposite direction*
>- Traffic altitude:  *nine thousand*

The problem here is that this information is not standardized in terms of which data and in which order are included in the command. 

So we can't define a single function (lambda function for the lexicon) that can accumulate all data about the traffic in all cases. The arity of the function and order, and types of its arguments are unknown in advance.

To solve the problem in the context of the CCG parser, we define multiple versions of the TRAFFICINFO function, each with a small number of arguments and use it as nested functions.  


```

PARSE (simplified JSON):

{
  "CALLSIGN": {
    "AIRCRAFT": "SkyWest",
    "INTNUMBER": "3124"
  },
  "TRAFFICINFO": {
    "TRAFFICINFO": {
      "TRAFFICINFO": {
        "TRAFFIC": "traffic",
        "CLOCKPOSITION": {
          "WORDNUMBER": "twelve",
          "CLOCKPOSITION": "oclock"
        }
      }
    },
    "DISTANCE": {
      "DISTANCE": "three",
      "DISTANCE": "miles"
    },
    "DIRECTION": {
      "DIRECTION": "opposite",
      "DIRECTION": "direction"
    },
    "ALTITUDE": {
      "ALTITUDE": {
        "ALTITUDE": "altitude",
        "IS_1": "indicates",
        "WORDNUMBER": {
          "WORDNUMBER": "nine",
          "WORDNUMBER": "thousand"
        }
      }
    }
  },
  "REPORT": {
    "REPORT": "Advise",
    "WHEN": "when",
    "WHO": "you have",
    "the TRAFFICINFO": {
      "TRAFFIC": "traffic",
      "STATUS": "in sight"
    }
  }
}
```

We see here these variants of the TRAFFICINFO function:

>- TRAFFICINFO ( TRAFFIC, CLOCKPOSITION )
>- TRAFFICINFO ( TRAFFICINFO, DISTANCE )
>- TRAFFICINFO ( TRAFFICINFO, DIRECTION )
>- TRAFFICINFO ( TRAFFICINFO, ALTITUDE )
>- TRAFFICINFO ( TRAFFIC, STATUS )

Here is one another example:

```
COMMAND: United 341 traffic 10 o’clock 3 miles crossing left to right same altitude Citabria.

PARSE (simplified JSON):

{
  "CALLSIGN": {
    "AIRCRAFT": "United",
    "INTNUMBER": "341"
  },
  "TRAFFICINFO": {
    "TRAFFICINFO": {
      "TRAFFICINFO": {
        "TRAFFICINFO": {
          "TRAFFICINFO": {
            "TRAFFICINFO": {
              "TRAFFICINFO": {
                "TRAFFIC": "traffic",
                "CLOCKPOSITION": {
                  "INTNUMBER": "10",
                  "CLOCKPOSITION": "oclock"
                }
              }
            },
            "DISTANCE": {
              "DISTANCE": "3",
              "DISTANCE": "miles"
            }
          }
        },
        "ONGOINGACTION": {
          "ONGOINGACTION": "crossing",
          "DIRECTION": "left to right"
        },
        "ALTITUDE": {
          "ALTITUDE": "same",
          "ALTITUDE": "altitude"
        }
      }
    },
    "AIRCRAFT": "Citabria"
  }
}
```

We see here new variants of the TRAFFICINFO function:

>- TRAFFICINFO ( TRAFFICINFO, ONGOINGACTION )
>- TRAFFICINFO ( TRAFFICINFO, AIRCRAFT )


## Scope of the HOLD instruction

Let's consider this ATC command:

```
COMMAND: Air France 9 hold at DOVER VOR standard right turns maintain flight level 270 Expect further clearance at 1530Z Contact London Control 132.
```

This means that the pilot should wait for new instructions (*further clearance*) over *DOVER VOR* fix executing *standard right turns* at *flight level 270*. If he didn't get new instructions on or before 15:30 Zulu then he should execute holding exit logic procedure. 

The question is when the pilot should contact *London Control* - just after he gets new instructions or before? Really, this means who is responsible for new instructions issue - current controller or the *London Control*?

I discussed this question with chatGPT and got this explanation:

```
You should contact London Control immediately.

1530Z is when you expect further clearance, not when you switch frequency.
```
But contact instruction doesn't belong to the HOLD scope:

```
HOLD is a flight procedure, CONTACT is a control relationship

They live in different semantic layers:

HOLD → aircraft trajectory behavior

CONTACT → air traffic control authority

They should not share scope.
```
Interesting. 

```
PARSE (simplified JSON):

{
  "CALLSIGN": {
    "AIRCRAFT": "Air France",
    "INTNUMBER": "9"
  },
  "HOLD": {
    "HOLD": {
      "HOLD": {
        "HOLD": {
          "HOLD": {
            "HOLD": {
              "HOLD": {
                "HOLD": "hold",
                "AT": "at",
                "FIX": {
                  "WAYPOINT": "DOVER",
                  "NAVAID": "VOR"
                }
              }
            },
            "TURNS": "standard right turns"
          }
        },
        "MAINTAIN": {
          "MAINTAIN": {
            "MAINTAIN": "maintain",
            "FLEVEL": {
              "FLEVEL": "flight level",
              "FLEVELVALUE": "270"
            }
          }
        }
      }
    },
    "EXPECT": {
      "EXPECT": {
        "EXPECT": "Expect",
        "CLEARANCE": {
          "CLEARANCE": "further clearance",
          "AT": "at",
          "TIMEINFO": "1530Z"
        }
      }
    }
  },
  "CONTACT": {
    "CONTACT": "Contact",
    "CONTROLLER": {
      "PLACE": "London",
      "CONTROLLER": {
        "CONTROLLER": "Control",
        "FREQUENCY": {
          "REALNUMBER": "132.7"
        }
      }
    }
  }
}
```

Functions used for HOLD parsing for this command:

>- HOLD ( HOLD, AT, FIX)
>- HOLD ( HOLD, TURNS)
>- HOLD ( HOLD, MAINTAIN)
>- HOLD ( HOLD, EXPECT)

And this is one another example related to the HOLD instruction.

```
COMMAND: American 105 heavy due traffic proceed direct DIXIE hold north on the Victor zero eight zero radial right turns expect further clearance one seven one zero Zulu Maintain flight level two four zero After holding proceed Victor 16 to Robbinsville then Tango 212 to Yardley then as filed

PARSE (simplified and condensed JSON):

{
  "CALLSIGN": {...},
  "REASON": {...},
  "NAVIGATION": {...},
  "HOLD": {
    "HOLD": {
      "HOLD": {
        "HOLD": {
          "HOLD": {
            "HOLD": {
              "HOLD": {
                "HOLD": {
                  "HOLD": "hold",
                  "POSITION": {
                    "DIRECTIONMAGNETIC": "north",
                    "ON": "on",
                    "the RADIAL": {
                      "ROUTE": "Victor zero eight zero",
                      "RADIAL": "radial"
                    }
                  }
                }
              },
              "TURNS": "right turns"
            }
          },
          "EXPECT": {
            "EXPECT": {
              "EXPECT": "expect",
              "CLEARANCE": "further clearance",
              "TIME": {
                "WORDNUMPHONEALPHABET": {
                  "WORDNUMBER": "one seven one zero",
                  "PHONETICALPHABET": "Zulu"
                }
              }
            }
          }
        }
      },
      "MAINTAIN": {
        "MAINTAIN": {
          "MAINTAIN": "Maintain",
          "FLEVEL": {
            "FLEVEL": "flight level",
            "FLEVELVALUE": "two four zero"
          }
        }
      }
    }
  },
  "NAVIGATION": {
    "AFTER": {
      "AFTER": "After",
      "HOLD": "holding"
    },
    "NAVIGATION": {...}
  },
  "THEN": {...},
  "THEN_3": {...}
}
```

Here for the HOLD parsing, these variants of the HOLD function are used to form a representation of its scope:

>- HOLD ( HOLD, POSITION )
>- HOLD ( HOLD, TURNS )
>- HOLD ( HOLD, EXPECT )
>- HOLD ( HOLD, MAINTAIN )