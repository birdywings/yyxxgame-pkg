# -*- coding: utf-8 -*-
"""
@File: method
@Author: ltw
@Time: 2024/2/18
"""
import pandas as pd


def new_user_model(**kwargs):
    """
    :param kwargs:
        first_day_arppu: 首日arppu, 例: 0.0
        after_first_day_arppu: 次日后arppu, 例: 0,0
        pay_rate: 付费率, 例: 0.0
        cal_days: 计算天数, 例: 360
        unit_price: 付费单价, 例: 0
        pay_keep_list: N日玩家留存, 例: [(2, 0.32), (7, 0.14), (30, 0.06), (90, 0.04)]
    :return:
        "注册天数","新增用户留存","用户付费率","ARPPU","LTV增加值","TLV","LTV倍数","RTLV","回本情况"
        res_df[
            ["day", "user_keep", "pay_rate", "arppu", "rltv_add", "ltv", "rltv_multiple", "rltv", "recover_rate"]
        ]
    """
    from yyxx_game_pkg.statistic.analysis.model import load_logarithmic_data

    first_day_arppu = kwargs["first_day_arppu"]
    after_first_day_arppu = kwargs["after_first_day_arppu"]
    pay_rate = kwargs["pay_rate"]
    cal_days = kwargs["cal_days"]
    unit_price = kwargs["unit_price"]
    pay_keep_list = kwargs["pay_keep_list"]

    # 计算累计付费留存[回归拟合计算]
    x_data = [val[0] for val in pay_keep_list]
    y_data = [val[1] for val in pay_keep_list]
    accumulate_pay_rate_list = load_logarithmic_data(x_data, y_data, cal_days)

    def init_data_list(data_len):
        return [i + 1 for i in range(data_len)]

    # day 付费天数
    # user_keep 新增用户留存
    # pay_rate 用户付费率
    # arppu ARPPU
    # rltv_add RLTV增加值（对应天数累计付费留存*老付费用户付费率*arppu）
    # ltv TLV （上一日的LTV+对应日的LTV增加值）
    # rltv_multiple RLTV倍数 （对应日的RLV/首日RLTV）
    # rltv RTLV （上一日的RLTV+对应日的RLTV增加值）
    # recover_rate 回本率 （对应天数RLTV/付费单价）
    data = {
        "day": init_data_list(cal_days),
        "user_keep": [1] + accumulate_pay_rate_list,
        "pay_rate": [pay_rate] * cal_days,
        "arppu": [first_day_arppu] + [after_first_day_arppu] * (cal_days - 1),
        "rltv_add": init_data_list(cal_days),
        "ltv": init_data_list(cal_days),
        "rltv_multiple": init_data_list(cal_days),
        "rltv": init_data_list(cal_days),
        "recover_rate": init_data_list(cal_days),
    }

    res_df = pd.DataFrame(data)

    # ltv增长值、ltv倍数计算
    res_df["rltv_add"] = (res_df["user_keep"] * res_df["pay_rate"] * res_df["arppu"]).round(2)
    res_df["ltv"] = res_df["rltv_add"].cumsum().round(2)
    res_df["rltv_multiple"] = (res_df["ltv"] / res_df["ltv"].iloc[0]).round(2)
    res_df["rltv"] = (res_df["arppu"].iloc[0] * (res_df["ltv"] / res_df["ltv"].iloc[0])).round(2)
    res_df["recover_rate"] = (res_df["rltv"] / unit_price).round(4)

    # 格式转化
    res_df["user_keep"] = res_df["user_keep"].apply(lambda x: f"{round(x * 100, 2)}%")
    res_df["pay_rate"] = res_df["pay_rate"].apply(lambda x: f"{round(x * 100, 4)}%")
    res_df["recover_rate"] = res_df["recover_rate"].apply(lambda x: f"{round(x * 100, 4)}%")

    res_df = res_df[
        ["day", "user_keep", "pay_rate", "arppu", "rltv_add", "ltv", "rltv_multiple", "rltv", "recover_rate"]
    ]
    return res_df


def pay_user_actual_model(source_df: pd.DataFrame) -> pd.DataFrame:
    """
    付费用户模型数据计算
    :param source_df: 原数据df, 具有列 ['cnt_day', 'pay_act_num', 'pay_money', 'pay_num']
        :cnt_day: 创角天数
        :pay_act_num: 对应创角天数付费留存
        :pay_money: 对应创角天数付费总金额
        :pay_num: 对应创角天数付费账号数
    :return: df数据
    """
    from utils import xdataframe

    data_df = source_df.copy().fillna(0).astype(int)
    data_df = (
        data_df.groupby(["cnt_day"]).agg({"pay_act_num": "sum", "pay_money": "sum", "pay_num": "sum"}).reset_index()
    )
    data_df = data_df.sort_values("cnt_day", ascending=True)
    # 累计付费留存: 对应天数的付费留存玩家/首日的付费留存玩家
    data_df["cumsum_pay"] = xdataframe.cal_round_rate(
        data_df["pay_act_num"] / data_df["pay_act_num"].iloc[0] * 100, suffix="", invalid_value="0.0"
    ).astype(float)
    data_df["cumsum_pay_rate"] = data_df["cumsum_pay"].astype(str) + "%"
    # 老付费用户付费率: 对应天数付费玩家数/在对应天数时的付费留存玩家
    data_df["old_pay"] = xdataframe.cal_round_rate(
        data_df["pay_num"] / data_df["pay_act_num"] * 100, suffix="", invalid_value="0.0"
    ).astype(float)
    data_df["old_pay_rate"] = data_df["old_pay"].astype(str) + "%"
    # ARPPU: 对应天数的充值总金额/对应天数付费玩家数
    data_df["arppu"] = xdataframe.cal_round_rate(
        data_df["pay_money"] / data_df["pay_num"], suffix="", invalid_value="0.0"
    ).astype(float)
    # RLTV增加值: 对应天数累计付费留存*老付费用户付费率*arppu
    data_df["rltv_add"] = xdataframe.cal_round_rate(
        data_df["cumsum_pay"] * data_df["old_pay"] * data_df["arppu"] / 10000, suffix="", invalid_value="0.0"
    ).astype(float)
    # RTLV: 上一日的RLTV+对应日的RLTV增加值
    data_df["rltv"] = data_df["rltv_add"].cumsum().round(2)
    # RLTV倍数: 对应日的RLV/首日RLTV
    data_df["rltv_mult"] = xdataframe.cal_round_rate(
        data_df["rltv"] / data_df["rltv"].iloc[0], suffix="", invalid_value="0.0"
    ).astype(float)
    data_df = data_df[["cnt_day", "cumsum_pay_rate", "old_pay_rate", "arppu", "rltv_add", "rltv", "rltv_mult"]]
    return data_df


def pay_user_forecast_model(
    *args,
    cal_days: int,
    day1_arppu: float,
    day2_arppu: float,
    day2_pay_rate: float,
    x_data: list,
    y_data: list,
    unit_price: float,
    **kwargs,
) -> pd.DataFrame:
    """
    付费用户模型预测
    !!! 请使用键值对进行传参 cal_days=30,day1_arppu=1.2
    :param args:忽略参数
    :param cal_days:预测天数
    :param day1_arppu:首日ARPPU
    :param day2_arppu:次日ARPPU
    :param day2_pay_rate:次日(及以后)付费率(非%)
    :param x_data: 对标数据-目标天数
    :param y_data: 对标数据-累计付费留存(非%)
    :param unit_price: 付费单价
    :param kwargs:忽略参数
    :return: df数据
    """
    from utils import xdataframe
    from statistic.analysis.model import load_logarithmic_data

    data_df = pd.DataFrame(
        {
            "cnt_day": range(1, cal_days + 1),
            "old_pay_rate": [1] + [day2_pay_rate] * (cal_days - 1),
            "arppu": [day1_arppu] + [day2_arppu] * (cal_days - 1),
            "cumsum_pay_rate": [1] + load_logarithmic_data(x_data, y_data, cal_days),
        }
    )
    # ltv增长值、ltv倍数计算
    data_df["rltv_add"] = (data_df["cumsum_pay_rate"] * data_df["old_pay_rate"] * data_df["arppu"]).round(2)
    # RTLV: 上一日的RLTV+对应日的RLTV增加值
    data_df["rltv"] = data_df["rltv_add"].cumsum().round(2)
    # RLTV倍数: 对应日的RLV/首日RLTV
    data_df["rltv_mult"] = xdataframe.cal_round_rate(
        data_df["rltv"] / data_df["rltv"].iloc[0], suffix="", invalid_value="0.0"
    ).astype(float)
    # 回本情况
    data_df["recove_rate"] = xdataframe.cal_round_rate(100 * data_df["rltv"] / unit_price, invalid_value="0.0")
    # 百分比转换
    data_df["old_pay_rate"] = xdataframe.cal_round_rate(100 * data_df["old_pay_rate"], invalid_value="0.0")
    data_df["cumsum_pay_rate"] = xdataframe.cal_round_rate(100 * data_df["cumsum_pay_rate"], invalid_value="0.0")
    data_df = data_df[
        ["cnt_day", "cumsum_pay_rate", "old_pay_rate", "arppu", "rltv_add", "rltv", "rltv_mult", "recove_rate"]
    ]
    return data_df
