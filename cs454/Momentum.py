from pytz import timezone
#################################################
# # Read me
  # This is an algorithm developed on quantopian.com. Quantopian provides a platform for algorithm trading, 
#################################################

#################################################
# # Strategy Outline

  # The main strategy is to keep an array of 10 chosen stocks and sort them on a daily basis according to their momentum, 
  # the momentum is calculated using a 1 day MA divided by a 2 day MA, in addition the MA has to be positive(tickup). 
  # Trades will then be done on the sorted array of stocks, it will buy the top N stocks, where N is a constant set at the 
  # top and close any positions thats outside the top N. 
  
  # While back testing this algorithm, I have noticed that for this kind of algorithm, it is very vulnerable to spike in prices, 
  # so I've included the stop loss function to handle spikes. Although trades are done on a daily basis, the stop loss function 
  # gets called every 30 mins to check if there are any sudden movements in stock price, if there is, close the position immediately 
  # to avoid further losses. 

##################################################



CHOSEN_SECURITIES = [sid(37945), sid(37515), sid(17455), sid(37514),sid(37083), sid(41575), sid(37049), sid(37048), sid(8554)] # Chosen_Securities contains an array of stocks that will be sorted on a daily basis based on their momentum

BALANCE_FREQUENCY = 1 # in days    (set 1 balance daily currently)

STOP_LOSS_FREQUENCY = 30 # in mins  (set to 30 mins currently)

Top_Stock_Chosen= 4 # constant to to pick the top N stocks ( current set to top 4 stocks)

COND1_USED = True # COND1 is fulfilled if short term SMA/ long term SMA > SAM_RATIO_LOWER_BOUND
SMA_RATIO_LOWER_BOUND = 1.0 # used for cond1

COND2_USED = True # the long term sma is said to be ticking up if it has been rising(not strictly) for (SMA_LONG_TICK_UP_PERIOD) days

SMA_LONG_TICK_UP_PERIOD = 1 # if SMA last day > SMA today, it is rising for 1 extra day, elif SMA last day > SMA today * SMA_LONG_TICK_UP_CONSTANT, it is keeping even,  else it is falling

SMA_LONG_TICK_UP_CONSTANT = .999 # used for cond2

STOP_LOSS_USED = True # enable stop loss

underperforming_PCT = .95 # stop loss constant for underperforming threashhold, it is currently set to 5%, so if olderprice/newprice is lower than 0.95 stop loss is triggered


#################################################
# # initialize function
  # initialize is called at the very beginning, it sets up all the default arrays that will be used and initialize them with their default values.

##################################################

def initialize(context):
    # initializing the default variables
    context.dayCount = -4;
    context.stocks = CHOSEN_SECURITIES  
    for stock in context.stocks: 
        context.smaShort = dict.fromkeys(context.stocks, 0.0) # initialize the sma short for every stock
        context.smaLong = dict.fromkeys(context.stocks, 0.0) # intiailize the sma long for every stock
        context.ratio = dict.fromkeys(context.stocks, 0.0) 
        context.cond = dict.fromkeys(context.stocks, True) 
        context.stopList = dict.fromkeys(context.stocks, 0.0)
        context.sorder = dict.fromkeys(context.stocks, 0.0) 
        context.tipup = dict.fromkeys(context.stocks, 0)  
    # setting up commision and slippage cost, which will include leverage cost    
    set_commission(commission.PerTrade(cost=6.0))
    set_slippage(slippage.FixedSlippage(spread=0.00))


#################################################
# # Stop loss function
  # The stop loss function is trigged every n minutes, where is n is a constant at the top, it will compare every 
  # stocks price against the most recent stock price, if the difference is more than underperforming_PCT (another constant at the top) 
  # it will close the position and sell every stock. Doing this insures that the algorithm is able to detect spikes in stock prices 
  # and close the positions before it drops too low

##################################################
def stop_loss(context, data):
    for stock in context.stocks:
        if stock in data:
            price = data[stock].price
            if context.stopList[stock] == 0.0:
                context.stopList[stock] = price
            difference = price/context.stopList[stock]
            if difference <= underperforming_PCT:            
                currentValue = context.portfolio.positions[stock].amount
                context.stopList[stock] = price
                order(stock, -currentValue)
            context.stopList[stock] = price
    pass


#################################################
# # trade function
  # the trade function is called on a daily basis, which will rebalance the portfolios according to the reranking 
  # and close all positions that cond_calc considers as negative momentum. The trade functions consists of two parts, 
  # a sell part and a buy part. The sell part will close all bad positions, and the buy part will buy in stocks that has high momentum 
    
##################################################
def trade(context, data):
    rank = 0
    benchMarkIndex = 0
    currentValue = 0
    orderAmount = 0
    numberChosen = 0;
    for stock in context.stocks:
        if stock == sid(8554): # determine the index of s&p 500
            benchMarkIndex = benchMarkIndex + 1 
    for stock in context.stocks: # close all bad positions here
        rank = rank + 1
        if context.cond[stock] == False or rank > Top_Stock_Chosen: # if the position is bad according to analysis, or it is not among the top earning stocks, close the positions.
            currentValue = context.portfolio.positions[stock].amount
            order(stock, -currentValue)
    rank = 0
    for stock in context.stocks: # determine the number of stocks where the momentum is positive, will be used later to determine the amount of stocks to buy when rebalancing the portfolio 
        rank = rank + 1
        if rank < Top_Stock_Chosen + 1:
            if context.cond[stock] == True:
                numberChosen = numberChosen + 1
    
    

    rank = 0
    for stock in context.stocks: # buy in new stocks which has positive momentum
        rank = rank + 1
        if rank < Top_Stock_Chosen + 1 or rank < benchMarkIndex + 1:
            currentValue = context.portfolio.positions[stock].amount # determine the current value held for the top n stocks. 
            if stock in data: # although it is obvious you have to buy in stocks with positive momentum, this part is used to determine the amount of stocks needed to buy to insure equal distribution, just incase one of the stock crashes
                if numberChosen == 0 or data[stock].price == 0:
                    orderAmount = 0
                else:
                    orderAmount = (context.portfolio.portfolio_value/numberChosen) / data[stock].price
            if context.cond[stock] == True: # if the stock has positive momentum then buy according to the calculated amount
                order(stock, orderAmount-currentValue)
    pass



#################################################
# # rerank function
  # this function is called on a daily basis to rerank the securities currently holding based on their momentum, the reranked securities 
  # will be used by the trade function to determine which stock to buy and which stock to sell
#################################################
    
def rerank(context, data):
    context = cond_calc(context)
    newlist = []
    for stock in context.stocks:
        newlist.append((context.cond[stock], context.ratio[stock], stock))
    context.stocks = [x for (z, y, x) in sorted(newlist, reverse = True)]
    return context


#################################################
# # long_trend_calc function
  # the long_trend_calc function is called on a daily basis by handle_data to determine how many days the long term 
  # moving average has been ticking up for each stock and store them in an array 
#################################################

def long_trend_calc(context, data):
    for stock in context.stocks:
        if stock in data:
            current_sma = data[stock].mavg(2) # current long sma is set to 2
        else:
            current_sma = 0
        if current_sma > context.smaLong[stock]: # if today's long sma is higher than yesterday's, increment tickup
            context.tipup[stock] += 1
        elif current_sma > (context.smaLong[stock] * SMA_LONG_TICK_UP_CONSTANT):
            continue;
        else:
            context.tipup[stock] = 0
    return context



#################################################
# # cond_calc function
  # check the condition for each stock in the array, if the condition is false, set the condition to false in a array, 
  # so the trade function will not buy, there are currently two conditions, cond1 checks if short term sma is > long term sma, 
  # cond2 checks if the stock is rising (tickup)
#################################################

def cond_calc(context):
    for stock in context.stocks:
        cond1 = (context.ratio[stock] > 1.0) 
        cond2 = (context.tipup[stock] >= SMA_LONG_TICK_UP_PERIOD)
        if COND1_USED:
            context.cond[stock] = cond1
        else:
            context.cond[stock] = True
        if COND2_USED:
            context.cond[stock] = (context.cond[stock] and cond2)
    return context





#################################################
# # handle data function
    # this is called by platform on each increment in time(can be minutely or daily)
    # 1.grab neccessary data
    # 2.rank according to ratios of (the periods are tentative) MA(30), MA(120) and the conditions
    # 3.keep track of time and call stoploss and trade
#################################################

def handle_data(context, data):
    local_time = get_datetime().astimezone(timezone('US/Eastern')) # set time zone
    if local_time.hour == 10 and local_time.minute == 0: # all analysis and trades are performed at 8 o clock
        context.dayCount += 1
        context =  long_trend_calc(context, data) # calculate the data trends
        for stock in context.stocks:
            if stock in data:
                context.smaShort[stock] = data[stock].mavg(1) # getting the long and short moving average for each stock
                context.smaLong[stock] = data[stock].mavg(2)
            if context.smaLong[stock] == 0:
                context.ratio[stock] = 0.0
                continue;
            context.ratio[stock] = context.smaShort[stock] / context.smaLong[stock] # calculate the ratio based on the moving averages
    if local_time.hour == 10 and STOP_LOSS_USED and context.dayCount%BALANCE_FREQUENCY != 0 : # trigger stop loss if necessary
        stop_loss(context,data)
    
    context = rerank(context, data) # rerank the stocks 
    if local_time.hour == 10 and local_time.minute == 0 and context.dayCount%BALANCE_FREQUENCY == 0: # trade stocks based on rerank
        trade(context, data)
    