# -*- coding: utf-8 -*-
'''
There is a risk of loss when trading stocks, futures, forex, options and other
tradeable finacial instruments. Please trade with capital you can afford to 
lose. Past performance is not necessarily indicative of future results. 
Nothing in this computer program/code is intended to be a recommendation and/or 
solicitation to buy or sell any stocks or futures or options or any 
tradable securities/financial instruments. 
All information and computer programs provided here is for education and 
entertainment purpose only; accuracy and thoroughness cannot be guaranteed. 
Readers/users are solely responsible for how to use these information and 
are solely responsible any consequences of using these information.

If you have any questions, please send email to IBridgePy@gmail.com
'''

def initialize(context):
    pass

def handle_data(context, data):
    request_data(historyData=[(symbol('SPY'), '1 min', '1 D'),
                              (symbol('AAPL'), '1 day', '10 D')  ])
    print ('Historical Data of SPY')
    print (data.data[symbol('SPY')].hist['1 min'].tail())
    print ('Historical Data of AAPL')
    print (data.data[symbol('AAPL')].hist['1 day'].tail())
    end()

          
  

