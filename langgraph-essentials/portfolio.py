'''
Scenario: 
A portfolio arrives. Three independent risk checks run on it — concentration, liquidity, credit. 
Their results get combined into one score. If the score is above the desk's tolerance, 
it goes to the investment committee. 
If not, it's approved automatically. Everything that happened is logged.
That's it. That's a real workflow you'd find on a risk desk, in about 200 lines.


    START
      |
      v
 [load_portfolio]
      |
  +---+---+--------------+          THREE CHECKS IN PARALLEL
  v       v              v
[concentration] [liquidity] [credit]
  |       |              |
  +---+---+--------------+
      v
  [aggregate]                       fan-in: combine into one score
      |
   +--+--+
 high   ok                          conditional edge
   |     |
   v     v
[escalate] [auto_approve]
   |     |
   +--+--+
      v
     END

'''