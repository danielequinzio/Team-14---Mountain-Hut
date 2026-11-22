TEMPLATE FOR RETROSPECTIVE (Team 14)  
Sprint 2
=====================================

The retrospective should include _at least_ the following
sections:

- [process measures](#process-measures)
- [quality measures](#quality-measures)
- [general assessment](#assessment)

## PROCESS MEASURES 

### Macro statistics

- Number of stories committed vs done : 4 vs 4
- Total points committed vs done : 21 vs 21
- Nr of hours planned vs spent (as a team) : 80h 15m vs **xxh:xxm**

**Remember**  a story is done ONLY if it fits the Definition of Done:
 
- Unit Tests passing
- Code review completed
- Code present on VCS
- End-to-End tests performed

> Please refine your DoD 

### Detailed statistics

| Story  | # Tasks | Points | Hours est. | Hours actual |
|--------|---------|--------|------------|--------------|
| _#0_   |   24    |    -   |    39h 15m |    38h 50m   |               
| _#5_   |    9    |    5   |     9h     |     8h 45m   |              
| _#6_   |    9    |    8   |    11h     |    10h 38m   |    
| _#7_   |   13    |    5   |    14h |    14h 10m   |
| _#8_   |    8    |    3   |     7h |     5h 12m   |

TOTAL TASKS: 63   

> place technical tasks corresponding to story `#0` and leave out story points (not applicable in this case)

- Hours per task  <span style="color:red">per person</span>  (average, standard deviation)

|        Member         |   Mean     |    StDev    |
|-----------------------|------------|-------------|
| Daniele Iacono        |  1h 19m    |    49m      | 
| Daniele Quinzio       |  1h 06m    |    43m      |
| Alessandro Marinari   |     50m    |    37m      |
| Dogukan Postoglu      |  1h 17m    |    49m      |
| Maximiliano Zurlo     |  1h 25m    |    55m      |  

- Total task estimation error ratio: sum of total hours estimation / sum of total hours spent -1

$$
\frac{\sum_i estimation_{task_i}}{\sum_i spent_{task_i}} - 1
= -0.0029
$$  


## QUALITY MEASURES 

- Unit Testing:
  - Total hours estimated: 6h
  - Total hours spent: 6h 15m
  - Nr of automated unit test cases:  127 tests
  - Coverage (if available): 100%
- Integration testing:
  - Total hours estimated: 5h
  - Total hours spent: 5h
- E2E testing:
  - Total hours estimated: 3h
  - Total hours spent: 3h 17m
- Code review: 
  - Total hours estimated: 5h 40m
  - Total hours spent: 4h 50m


## ASSESSMENT

- What caused your errors in estimation (if any)?
  
  During this sprint we underestimated the story points for MH-07. When we estimated it, we didn't account for guest registration, even though the clarifications explicitly required it. As a result, MH-07 was rated only 5 points but needed about 14h of work: more than MH-06 (8 points, 11h) and well above MH-05 (5 points, 9h). Its story points are therefore not consistent with the effort compared to the other stories.


- What lessons did you learn (both positive and negative) in this sprint?

  Good: The team meetings we held during the sprint improved our coordination and helped us work better together.

  Negative: Adapting previously implemented features to support the new requirements took more time than building new features from scratch, and we should take this into account for future estimating.

- Which improvement goals set in the previous retrospective were you able to achieve? 

  This time we held the sprint planning in the first days of the sprint, so everyone could start working on their tasks right away. We also kept a more consistent pace throughout the sprint, which meant we didn't end up doing most of the work at the last minute.
  
- Which ones you were not able to achieve? Why?

  Our communication improved compared to the previous sprint, but it still needs work, especially between the frontend and backend developers.
  
- Improvement goals for the next sprint and how to achieve them (technical tasks, team coordination, etc.)

  - Improve communication between frontend and backend developers, using our meetings and group chat to keep each other updated and work better together.
  - Agree on a clear Git workflow (branch naming and merging rules) and stick to it, so we avoid confusion caused by too many branches.

- One thing you are proud of as a Team!!

  We completed all the stories we committed to and also fixed the issues left over from the previous sprint!
