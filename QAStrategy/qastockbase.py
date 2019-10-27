#


"""
stock_base
"""
import datetime
import json
import os
import threading

import pandas as pd
import pymongo
from qaenv import (eventmq_ip, eventmq_password, eventmq_port,
                   eventmq_username, mongo_ip)

import QUANTAXIS as QA
from QAPUBSUB.consumer import subscriber_topic
from QAPUBSUB.producer import publisher_routing
from QAStrategy.qactabase import QAStrategyCTABase
from QIFIAccount import QIFI_Account


class QAStrategyStockBase(QAStrategyCTABase):

    def __init__(self, code='rb1905', frequence='1min', strategy_id='QA_STRATEGY', risk_check_gap=1, portfolio='default',
                 start='2019-01-01', end='2019-10-21',
                 data_host=eventmq_ip, data_port=eventmq_port, data_user=eventmq_username, data_password=eventmq_password,
                 trade_host=eventmq_ip, trade_port=eventmq_port, trade_user=eventmq_username, trade_password=eventmq_password,
                 taskid=None, mongo_ip=mongo_ip):
        super().__init__(code=code, frequence=frequence, strategy_id=strategy_id, risk_check_gap=risk_check_gap, portfolio=portfolio,
                         start=start, end=end,
                         data_host=eventmq_ip, data_port=eventmq_port, data_user=eventmq_username, data_password=eventmq_password,
                         trade_host=eventmq_ip, trade_port=eventmq_port, trade_user=eventmq_username, trade_password=eventmq_password,
                         taskid=taskid, mongo_ip=mongo_ip)

        self.code = code

    def subscribe_data(self, code, frequence, data_host, data_port, data_user, data_password):
        """[summary]

        Arguments:
            code {[type]} -- [description]
            frequence {[type]} -- [description]
        """
        self.sub = subscriber_topic(exchange='realtime_stock_{}'.format(
            frequence), host=data_host, port=data_port, user=data_user, password=data_password, routing_key='')
        for item in code:
            self.sub.add_sub(exchange='realtime_stock_{}'.format(
                frequence), routing_key=item)
        self.sub.callback = self.callback

    def upcoming_data(self, new_bar):
        """upcoming_bar :

        Arguments:
            new_bar {json} -- [description]
        """
        self._market_data = pd.concat([self._old_data, new_bar])
        # QA.QA_util_log_info(self._market_data)

        if self.isupdate:
            self.update()
            self.isupdate = False

        self.update_account()
        # self.positions.on_price_change(float(new_bar['close']))
        self.on_bar(new_bar)

    def ind2str(self, ind, ind_type):
        z = ind.tail(1).reset_index().to_dict(orient='records')[0]
        return json.dumps({'topic': ind_type, 'code': self.code, 'type': self.frequence, 'data': z})

    def callback(self, a, b, c, body):
        """在strategy的callback中,我们需要的是

        1. 更新数据
        2. 更新bar
        3. 更新策略状态
        4. 推送事件

        Arguments:
            a {[type]} -- [description]
            b {[type]} -- [description]
            c {[type]} -- [description]
            body {[type]} -- [description]
        """

        self.new_data = json.loads(str(body, encoding='utf-8'))
        self.running_time = self.new_data['datetime']
        if float(self.new_data['datetime'][-9:]) == 0:
            self.isupdate = True
        self.acc.on_price_change(self.new_data['code'], self.new_data['close'])
        bar = pd.DataFrame([self.new_data]).set_index(['datetime', 'code']
                                                      ).loc[:, ['open', 'high', 'low', 'close', 'volume']]
        self.upcoming_data(bar)

    def run_sim(self):
        self.running_mode = 'sim'

        self._old_data = QA.QA_fetch_stock_min(self.code, QA.QA_util_get_last_day(
            QA.QA_util_get_real_date(str(datetime.date.today()))), str(datetime.datetime.now()), format='pd', frequence=self.frequence).set_index(['datetime', 'code'])

        self._old_data = self._old_data.loc[:, [
            'open', 'high', 'low', 'close', 'volume']]

        self.database = pymongo.MongoClient(mongo_ip).QAREALTIME

        self.client = self.database.account
        self.subscriber_client = self.database.subscribe

        self.acc = QIFI_Account(
            username=self.strategy_id, password=self.strategy_id, trade_host=mongo_ip)
        self.acc.initial()

        self.pub = publisher_routing(exchange='QAORDER_ROUTER', host=self.trade_host,
                                     port=self.trade_port, user=self.trade_user, password=self.trade_password)

        self.subscribe_data(self.code, self.frequence, self.data_host,
                            self.data_port, self.data_user, self.data_password)

        self.add_subscriber('oL-C4w1HjuPRqTIRcZUyYR0QcLzo')
        self.database.strategy_schedule.job_control.update(
            {'strategy_id': self.strategy_id},
            {'strategy_id': self.strategy_id, 'taskid': self.taskid,
             'filepath': os.path.abspath(__file__), 'status': 200}, upsert=True)

        # threading.Thread(target=, daemon=True).start()
        self.sub.start()

    def run(self):
        while True:
            pass

    def update_account(self):
        if self.running_mode == 'sim':
            QA.QA_util_log_info('{} UPDATE ACCOUNT'.format(
                str(datetime.datetime.now())))

            self.accounts = self.acc.account_msg
            self.orders = self.acc.orders
            self.positions = self.acc.positions

            self.trades = self.acc.trades
            self.updatetime = self.acc.dtstr
        elif self.running_mode == 'backtest':
            #self.positions = self.acc.get_position(self.code)
            self.positions = self.acc.positions


if __name__ == '__main__':
    QAStrategyStockBase(code=['000001', '000002']).run_sim()
