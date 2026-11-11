TEMPLATE FOR RETROSPECTIVE (Team 14)
Sprint 1
=====================================

The retrospective should include _at least_ the following
sections:

- [process measures](#process-measures)
- [quality measures](#quality-measures)
- [general assessment](#assessment)

## PROCESS MEASURES 

### Macro statistics

- Number of stories committed vs done : 4 vs 4
- Total points committed vs done : 19 vs 19
- Nr of hours planned vs spent (as a team) : 80h 5m vs 80h 19m

**Remember**  a story is done ONLY if it fits the Definition of Done:
 
- Unit Tests passing
- Code review completed
- Code present on VCS
- End-to-End tests performed

> Please refine your DoD 

### Detailed statistics

| Story  | # Tasks | Points | Hours est. | Hours actual |
|--------|---------|--------|------------|--------------|
| _#0_   |   20    |    -   |    38h 30m |    38h 50m   |               
| _#1_   |   11    |    8   |    17h     |    17h 15m   |              
| _#2_   |   10    |    5   |    11h     |    11h 50m   |    
| _#3_   |    9    |    3   |     7h 50m |     7h 35m   |
| _#4_   |    7    |    3   |     5h 45m |     5h 12m   |

TOTAL TASKS: 57   

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

  We did not have great errors in estimation, only by some minutes less or more with 30m as the highest gap. We underestimated/overestimated the time because we didn't consider some aspects related to those tasks.

- What lessons did you learn (both positive and negative) in this sprint?

  Good: Defining more precise tasks helped us with task assignment and estimation.
  Negative: We should plan our sprint as soon as possible so we can balance our workload.

- Which improvement goals set in the previous retrospective were you able to achieve? 

  We improved our meetings defining more specific tasks and explaining better how the work should be done. We also defined code review tasks.
  
- Which ones you were not able to achieve? Why?

  We improved our task division but we still need to improve our task definition and communication during meetings because this time we still had two tasks which required more than 2h (even if the estimated time was 2h).
  
- Improvement goals for the next sprint and how to achieve them (technical tasks, team coordination, etc.)

  We should get working to the sprint as soon as possible so we shouldn't have the planning meeting too late.  
  Everyone should start working (and keep the others updated) at their tasks right after the planning so we don't get most of the work done just few days before the deadline. 

- One thing you are proud of as a Team!!

  We managed to get done all the stories committed not exceeding the estimated time.
