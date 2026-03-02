from datetime import datetime
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class StrongTrend_Retest_4H(IStrategy):

    # --- Grundeinstellungen ---
    timeframe = '4h'
    startup_candle_count = 200
    can_short = False

    use_custom_stake_amount = True  # Aktiviert Risk Scaling

    # --- Risk / Reward ---
    minimal_roi = {
        "0": 0.07
    }

    stoploss = -0.025
    trailing_stop = False

    # ================================
    # INDICATORS
    # ================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['ema200'] = ta.EMA(dataframe['close'], timeperiod=200)
        dataframe['ema50'] = ta.EMA(dataframe['close'], timeperiod=50)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # Breakout-Level (letzte 15 Kerzen Hoch)
        dataframe['high_15'] = dataframe['high'].rolling(15).max()

        return dataframe

    # ================================
    # ENTRY
    # ================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        breakout = dataframe['close'] > dataframe['high_15'].shift(1)

        retest = (
            (dataframe['low'] < dataframe['high_15'].shift(1)) &
            (dataframe['close'] > dataframe['high_15'].shift(1))
        )

        bullish_candle = dataframe['close'] > dataframe['open']
        above_ema50 = dataframe['close'] > dataframe['ema50']

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema200']) &
                (dataframe['ema50'] > dataframe['ema200']) &
                (dataframe['adx'] > 22) &
                (breakout.shift(1)) &
                (retest) &
                (bullish_candle) &
                (above_ema50)
            ),
            'enter_long'
        ] = 1

        return dataframe

    # ================================
    # EXIT
    # ================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ================================
    # RISK SCALING (1% pro Trade)
    # ================================
    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float,
        max_stake: float,
        leverage: float,
        entry_tag: str,
        side: str,
        **kwargs,
    ) -> float:

        risk_per_trade = 0.01  # 1% Risiko pro Trade
        stoploss = abs(self.stoploss)

        balance = self.wallets.get_total_stake_amount()

        risk_amount = balance * risk_per_trade
        stake = risk_amount / stoploss

        # Sicherheitsbegrenzung
        return min(stake, max_stake)

