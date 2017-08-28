# Algorithm uses front month and second month settlement prices for VIX futures to 
# determine whether or not to short the ETF VXX. Current threshold is 0.95 representing 
# the percentage contango of F1/F2. If the settlements F1/F2 is below 0.95, short VXX, 
# otherwise move to cash.
import datetime as dt
import numpy as np
import pandas as pd
import pandas.stats.moments as st

#%%        
# Post Function for fetch_csv where futures data from Quandl is standardized
def initialize(context):    
    # Declaring VXX as the stock for shorting
    context.vxx = symbol('VXX')
    context.spy = symvol('SPY')
    
    context.vxx_pct = 1
    context.pf_target = 20000
    context.stop_loss_threshold = 1.02
    context.buyback_threshold = 1.025
    context.spy_threshold = 0.99
    context.augen_period = 21
    context.augen_threshold = -1.5
    context.max_vix = 30
    #context.target_mv = 50000
    
    # Scheduling the order function to occur everyday 5 minutes after market open
    schedule_function(my_rebalance, date_rules.every_day(), time_rules.market_open(hours = 0, minutes = 5))
    
    schedule_function(stop_loss, date_rules.every_day(), time_rules.market_close(hours = 0, minutes = 1))
    
    time_interval = 30
    
    total_minutes = 6*60 + (60 - time_interval)
    
    for i in range(1, total_minutes):
        # Every 30 minutes run schedule
        if (i == 1) or (i % time_interval == 0):
            # This will start at 9:31AM and will run every 30 minutes
            schedule_function(stop_loss, date_rules.every_day(), time_rules.market_open(minutes=i),True)
    
    # Setting trading gurads
    # set_max_order_count(5)

#%%
def maturities(context,data):
    
    # Calculate today, but note that since we are adjusting for lookback bias, we need to change the current date to one day prior
    if get_datetime().to_datetime().date().weekday() == 0:
        today = get_datetime().to_datetime().date()# - dt.timedelta(3)
    else:
        today = get_datetime().to_datetime().date()# - dt.timedelta(1)
    curr_month = today.month
    curr_year = today.year
    
    # Finding Prev Third Wed
    curr_eigth_day = dt.date(curr_year,curr_month,7)
    curr_second_day = dt.date(curr_year,curr_month,3).weekday()
    curr_third_fri = curr_eigth_day - dt.timedelta(curr_second_day) + dt.timedelta(14)
    last_third_wed = curr_third_fri - dt.timedelta(30)
    
    # Finding Next Third Wed
    if curr_month == 12:
        next_month = 2
        next_year = curr_year + 1
    elif curr_month == 11:
        next_month = 1
        next_year = curr_year + 1
    else:
        next_month = curr_month + 2
        next_year = curr_year
    next_eigth_day = dt.date(next_year,next_month,7)
    next_second_day = dt.date(next_year,next_month,3).weekday()
    next_third_fri = next_eigth_day - dt.timedelta(next_second_day) + dt.timedelta(14)
    next_third_wed = next_third_fri - dt.timedelta(30)
    
    # Finding Cur Third Wed
    if curr_month == 12:
        next_month = 1
        next_year = curr_year + 1
    else:
        next_month = curr_month + 1
        next_year = curr_year
    next_eigth_day = dt.date(next_year,next_month,7)
    next_second_day = dt.date(next_year,next_month,3).weekday()
    next_third_fri = next_eigth_day - dt.timedelta(next_second_day) + dt.timedelta(14)
    curr_third_wed = next_third_fri - dt.timedelta(30)
    
    # Finding Term: When current date is after expiry, should be 100% of spot/f1
    if today < curr_third_wed:
        dte = curr_third_wed - today
        term = curr_third_wed - last_third_wed
    else:
        dte = next_third_wed - today
        term = next_third_wed - curr_third_wed
    # print (float(dte.days)/term.days)
    front_weight = float(dte.days)/term.days
    return front_weight

#%%
def before_trading_start(context,data):
    # Pulling VIX
    vix = pd.read_csv('http://www.cboe.com/publish/scheduledtask/mktdata/datahouse/vixcurrent.csv')
    vix.columns = ['Date','Open','High','Low','Close']
    vix = vix[1:]
    vix['Date'] = pd.to_datetime(vix['Date'])
    vix = vix.set_index(pd.DatetimeIndex(vix['Date']))
    
    # Getting VIX last close
    vx = float(vix[-1:].Close[0])
    
    # Pulling Futures Data
    vc = pd.read_csv('http://cfe.cboe.com/market-data/futures-settlements')
    vc.columns = ['Symbol','settle']
    vc['expiry'] = pd.to_datetime(vc['Symbol'].str.split(' ').str.get(1))
    vc['name'] = vc['Symbol'].str.split(' ').str.get(0)
    vc = vc[vc['name'] == 'VX'][['Symbol','settle','expiry']]
    vc = vc[vc['expiry'] > dt.datetime.today().date()]
    vc = vc.reset_index()
    
    # Getting Settlements of V1 and V2
    v1 = vc['settle'][0]
    v2 = vc['settle'][1]
    
    spot_wgt = maturities(context,data)
    front_wgt = 1 - spot_wgt
    
    context.threshold = 0.95
        
    # Creating ratio from weighting
    sf1_ratio = vx/v1
    f1f2_ratio = v1/v2
    #print"Front weight: %.6f"%spot_wgt
    #print "V1: %.4f" %data.current('v1','price')
    context.last_ratio = spot_wgt*sf1_ratio + front_wgt*f1f2_ratio
    #print "Contango: %.6f"%context.last_ratio
    context.signal = (context.last_ratio < context.threshold) and (vx < context.max_vix)
    # context.open_price = data.current(context.vxx,'close')
    
    # Pulling spy_hist
    request_data(historyData=[(context.spy, '1 day', '22 D') ])
    spy_hist = data[context.spy].hist['1 day']['close']
    log_returns = np.log(spy_hist) - np.log(spy_hist.shift(1))
    daily_vol = st.rolling_std(log_returns, context.augen_period, ddof = 1)
    daily_vol_dollar = (np.exp(daily_vol)-1)*spy_hist
    context.dollar_vol = daily_vol_dollar.ix[-1]
    
    context.spy_last_close = data.current(context.spy,'close')
    
    context.stop_loss_initializer = False
    context.stop_loss_not_triggered = True
    context.buyback_not_triggered = True

def stop_loss(context, data):
    
    if context.signal and context.stop_loss_not_triggered and context.stop_loss_initializer:
        context.current_price = data.current(context.vxx, 'price')
        context.price_change = context.current_price/context.open_price
        context.vxx_trigger = context.price_change > context.stop_loss_threshold
        
        context.spy_diff = data.current(context.spy,'price') - context.spy_last_close
        context.augen_vol = context.spy_diff/context.dollar_vol
        context.augen_trigger = context.augen_vol < context.augen_threshold
        if context.vxx_trigger:
            if context.vxx in context.portfolio.positions:
                #print "Stop loss reached - %.4f" %(context.price_change-1)
                order_target(context.vxx, 0)
                context.open_price = context.current_price
                context.stop_loss_not_triggered = False
                
    if not context.stop_loss_initializer:
        context.stop_loss_initializer = True
        context.open_price = data.current(context.vxx,'open')     
                
    if (context.stop_loss_not_triggered == False) and context.buyback_not_triggered:
        if context.signal:
            context.current_price = data.current(context.vxx, 'price')
            context.drop_price_change = context.current_price/context.open_price
            context.drop_trigger = context.drop_price_change > context.buyback_threshold
            context.spy_diff = data.current(context.spy,'price')-context.spy_last_close
            context.augen_vol = context.spy_diff/context.dollar_vol
            context.augen_trigger = context.augen_vol > context.augen_threshold
            if context.augen_trigger and context.drop_trigger:
                context.open_price = context.current_price
                target_mv = context.portfolio.portfolio_value
                vxx_mv = -target_mv*context.vxx_pct#-min(target_mv*context.vxx_pct,context.target_mv)
                vxx_amount = vxx_mv/data.current(context.vxx,'price')
                order_target(context.vxx,vxx_amount)
                #print "Buyback reached - %.4f" %(context.drop_price_change-1)
                spy_return = data.current(context.spy,'price')/context.spy_last_close
                #print "SPY Return: %.4f" %(spy_return - 1)
                # context.stop_loss_not_triggered = True
                context.buyback_not_triggered = False
    
def my_rebalance(context, data):
    # Specifying the contango ratio threshold to short VXX
    log.info(context.portfolio.cash)
    if context.signal:
        if context.vxx in context.portfolio.positions:
            #log.info("Already in - %.4f" %context.last_ratio)
            pass
        else:
            # Calculating the number of shares of VXX to short to reach the target
            # portfolio percentage allocation
            target_mv = context.portfolio.portfolio_value
            vxx_mv = -target_mv*context.vxx_pct#-min(target_mv*context.vxx_pct,context.target_mv)
            vxx_amount = vxx_mv/data.current(context.vxx,'price')
            order_target(context.vxx,vxx_amount)
            #log.info("Short - %.4f" %context.last_ratio)
    else:
        # If the contango ratio is above specified threshold, purchase back VXX shares and remain in cash
        order_target(context.vxx,0)
        log.info("Move to cash - %.4f" %context.last_ratio)
    vxx_record = context.portfolio.positions[context.vxx].amount
            
    #record(vxx_shares=vxx_record,ratio_vxx=context.last_ratio)
def handle_data(context,data):
    pass
    
    