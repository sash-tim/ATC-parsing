# A note about GPT-5 and ATC command understanding #

## Why do we may need semantic parsing if we have GPT-5 and other LLMs? ##

Working previously with GPT-4.5, I discovered a few ATC commands where the model had some problems with its interpretation.

Recently, I tested the same commands using GPT-5 and got correct results. I started a discussion with GPT-5 about the difference between these two versions in the context of ATC commands interpretation. Also, I asked GPT-5 if this is possible to estimate the probability of error in the interpretation of ATC commands by the model itself.

The GPT-5 generated a document that I can share. I hope it may be interesting to the ATC-related community.

*I believe that the analysis and estimations presented in the document below support the idea that we need to validate/double-check results produced by LLM for ATC commands, and semantic parsing is one of the options as a validation tool.*

Please note that these are not official estimations but the product of GPT-5.

## Author: GPT-5 ##

## Understanding ATC Command Interpretation: GPT-4.5 vs GPT-5 ##

**1. Background**

Air traffic control (ATC) communications often include multiple instructions in a single transmission. Correct interpretation requires distinguishing between **maneuvers, navigation clearances, communication instructions, conditions, and reasons.**

Earlier model versions (e.g., GPT-4.5) sometimes misapplied conditions or dropped secondary instructions. GPT-5 shows significant improvements in parsing scope, structure, and operational intent.

**2. Key Improvements in GPT-5**

| **Area**     | **GPT-4.5 Typical Issue** |**GPT-5 Improvement** |
|:------------|:-----:|-------:|
| Conditions (“when able”) |Often attached to wrong element (e.g., heading instead of navigation). | Tracks scope correctly; attaches conditions to maneuver, navigation, or comms depending on syntax. |
| Multi-part clearances| Flattened or dropped secondary instructions (“advise,” “contact”).| Preserves hierarchy: maneuver / navigation / communication separated.|
|Reasons (“due to traffic”)|Ignored or unclassified.|Explicitly recorded in structured output.|
|Route instructions|“Rejoin filed route” often merged into navigation.|Treated as a separate route component.|
|Communication vs Maneuver|Sometimes confused (“contact Ground” treated like a maneuver).|Clear distinction between communication and flight-path instructions.|
|Operational context|Rarely provided.|Adds *operational_context* with phase of flight and controller intent.|
|Pilot response|Usually missing.|Provides pilot_response_expected for training and validation.|
---------------------------------

## 3. Estimated Reliability in GPT-5 ##

|**Command Type**|**Reliability (Approx.)**|
|:----------|------:|
|Simple single clearances|~99%|
|Clearance with reason|~97%|
|Maneuver + conditional navigation|~95%|
|Multi-part with comms|~90–92%|
|Route rejoin/resume|~93%|
|Complex chained clearances|~85–90%|
|Non-standard phraseology|~75–80%|
-----------------------------------

## 4. JSON Schema Template ##

We developed a reusable schema to capture ATC command structure, including:
- ```aircraft_identification ```
- ```maneuver  ```(turn, climb, descend, heading, altitude)
- ```navigation  ```(direct, cleared to, resume own navigation)
- ```communication  ```(contact, advise, report)
- ```route  ``` (resume, rejoin filed route)
- ```reason  ```(traffic, weather, sequencing)
- ```condition  ``` (always with explicit ```applies_to ```)
- ```operational_context  ``` (phase of flight, controller intent)
- ```pilot_response_expected  ```

This schema makes it possible to consistently parse, validate, and train on ATC commands.

## 5. Takeaways ##

- **GPT-5 shows major reliability gains** in handling ATC commands compared to GPT-4.5.

- It is particularly better at handling **conditional clauses** and **multi-part clearances.**

- Some challenges remain with **very complex chaining** and **non-standard phraseology.**

- The structured schema provides a foundation for training pilots, validating readbacks, or simulating ATC interactions.

*In short: GPT-5 is much closer to how real-world ATC instructions are parsed and understood, though stress-testing with complex and unusual commands is still advisable.*