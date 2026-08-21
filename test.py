from __future__ import annotations

from datetime import date, timedelta
import io

import pandas as pd
import plotly.express as px
import streamlit as st


COLUMNS = [
	"客户",
	"项目",
	"测试人员",
	"版本",
	"版本类型",
	"开始日期",
	"结束日期",
	"投入人力",
	"是否为废弃版本",
	"废弃版本人力",
	"废弃原因",
]

VERSION_TYPE_OPTIONS = ["mr", "smr", "在研"]


def month_start(day: date) -> date:
	return day.replace(day=1)


def month_end(day: date) -> date:
	next_month = day.replace(day=28) + timedelta(days=4)
	return next_month - timedelta(days=next_month.day)


def empty_dataframe() -> pd.DataFrame:
	return normalize_dataframe(pd.DataFrame(columns=COLUMNS))
def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
	normalized = df.copy()
	for col in COLUMNS:
		if col not in normalized.columns:
			normalized[col] = pd.NA

	normalized["客户"] = normalized["客户"].astype("string").fillna("")
	normalized["项目"] = normalized["项目"].astype("string").fillna("")
	normalized["测试人员"] = normalized["测试人员"].astype("string").fillna("")
	normalized["版本"] = normalized["版本"].astype("string").fillna("")
	normalized["版本类型"] = normalized["版本类型"].astype("string").str.lower().fillna("")
	normalized["版本类型"] = normalized["版本类型"].apply(lambda x: x if x in VERSION_TYPE_OPTIONS else "在研")
	normalized["废弃原因"] = normalized["废弃原因"].astype("string").fillna("")

	for col in ["开始日期", "结束日期"]:
		normalized[col] = pd.to_datetime(normalized[col], errors="coerce").dt.date

	normalized["投入人力"] = pd.to_numeric(normalized["投入人力"], errors="coerce").fillna(0.0)
	normalized["废弃版本人力"] = pd.to_numeric(normalized["废弃版本人力"], errors="coerce").fillna(0.0)

	bool_map = {
		"true": True,
		"false": False,
		"1": True,
		"0": False,
		"是": True,
		"否": False,
		"y": True,
		"n": False,
	}

	def to_bool(value: object) -> bool:
		if isinstance(value, bool):
			return value
		if pd.isna(value):
			return False
		return bool_map.get(str(value).strip().lower(), False)

	normalized["是否为废弃版本"] = normalized["是否为废弃版本"].apply(to_bool).astype("bool")
	discard_bool = normalized["是否为废弃版本"].to_numpy()
	normalized.loc[~normalized["是否为废弃版本"], "废弃版本人力"] = 0.0
	normalized.loc[~normalized["是否为废弃版本"], "废弃原因"] = ""
	empty_reason = normalized["废弃原因"].str.strip().to_numpy() == ""
	normalized.loc[discard_bool & empty_reason, "废弃原因"] = "其他"

	normalized = normalized[COLUMNS]
	return normalized


def read_csv_bytes(data: bytes) -> pd.DataFrame:
	last_error: Exception | None = None
	for encoding in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
		try:
			return pd.read_csv(io.BytesIO(data), encoding=encoding)
		except UnicodeDecodeError as exc:
			last_error = exc
	raise ValueError(f"无法识别 CSV 文件编码：{last_error}")


def read_uploaded_file(file_name: str, data: bytes) -> pd.DataFrame:
	lower_name = file_name.lower()
	if lower_name.endswith(".csv"):
		df = read_csv_bytes(data)
	elif lower_name.endswith(".xlsx"):
		df = pd.read_excel(io.BytesIO(data), engine="openpyxl")
	elif lower_name.endswith(".xls"):
		try:
			df = pd.read_excel(io.BytesIO(data), engine="xlrd")
		except ImportError:
			raise ValueError("读取 .xls 需要安装 xlrd，请将文件另存为 .xlsx 后重新上传。") from None
	else:
		raise ValueError("不支持的文件类型，请上传 .xlsx / .xls / .csv 文件。")

	missing_cols = [col for col in COLUMNS if col not in df.columns]
	if missing_cols:
		raise ValueError(f"文件缺少必需列：{'、'.join(missing_cols)}")
	return normalize_dataframe(df)


FILTER_WIDGET_KEYS = [
	"filter_time_mode",
	"filter_quick_range",
	"filter_start_date",
	"filter_end_date",
	"filter_discard",
	"filter_customers",
	"filter_projects",
	"filter_types",
	"filter_testers",
	"filter_reasons",
	"filter_version_kw",
]


def reset_filter_state() -> None:
	for key in FILTER_WIDGET_KEYS:
		st.session_state.pop(key, None)


def filter_by_date(df: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
	end_dates = pd.to_datetime(df["结束日期"], errors="coerce").dt.date
	mask = end_dates.between(start_date, end_date)
	return df.loc[mask].copy()


def add_month_column(df: pd.DataFrame) -> pd.DataFrame:
	with_month = df.copy()
	end_dt = pd.to_datetime(with_month["结束日期"], errors="coerce")
	with_month["结束日期_dt"] = end_dt
	with_month["结束月份"] = end_dt.dt.strftime("%Y-%m")
	with_month["结束年份"] = end_dt.dt.year.astype("Int64")
	with_month["结束周"] = end_dt.dt.to_period("W-MON").astype("string")
	return with_month


def filter_by_discard_status(df: pd.DataFrame, discard_filter: str) -> pd.DataFrame:
	if discard_filter == "仅废弃版本":
		return df[df["是否为废弃版本"]].copy()
	if discard_filter == "仅非废弃版本":
		return df[~df["是否为废弃版本"]].copy()
	return df.copy()


def apply_dimension_filters(
	df: pd.DataFrame,
	selected_customers: list[str],
	selected_projects: list[str],
	selected_types: list[str],
	selected_discard_reasons: list[str],
	version_keyword: str,
) -> pd.DataFrame:
	filtered = df.copy()
	if selected_customers:
		filtered = filtered[filtered["客户"].isin(selected_customers)]
	if selected_projects:
		filtered = filtered[filtered["项目"].isin(selected_projects)]
	if selected_types:
		filtered = filtered[filtered["版本类型"].isin(selected_types)]
	if selected_discard_reasons:
		filtered = filtered[filtered["废弃原因"].isin(selected_discard_reasons)]
	if version_keyword.strip():
		kw = version_keyword.strip().lower()
		filtered = filtered[filtered["版本"].str.lower().str.contains(kw, na=False)]
	return filtered.copy()


def rate_percent(numerator: float, denominator: float) -> float:
	if denominator <= 0:
		return 0.0
	return numerator / denominator * 100.0


def get_window_range(window_mode: str, anchor_date: date) -> tuple[date, date]:
	if window_mode == "月":
		return anchor_date - timedelta(days=29), anchor_date
	if window_mode == "半年":
		return anchor_date - timedelta(days=182), anchor_date
	return anchor_date - timedelta(days=365), anchor_date


def render_bar_chart(
	df: pd.DataFrame,
	x_col: str,
	y_col: str,
	color_col: str | None = None,
	title: str | None = None,
	barmode: str = "group",
	text_template: str = "%{y}",
) -> None:
	fig = px.bar(
		df,
		x=x_col,
		y=y_col,
		color=color_col,
		barmode=barmode,
		text_auto=True,
		title=title,
	)
	fig.update_traces(textposition="outside", cliponaxis=False, texttemplate=text_template)
	fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), legend_title_text="")
	st.plotly_chart(fig, use_container_width=True)


def render_line_chart(
	df: pd.DataFrame,
	x_col: str,
	y_col: str,
	color_col: str | None = None,
	title: str | None = None,
	text_template: str = "%{y}",
	show_all_labels: bool = True,
) -> None:
	fig = px.line(
		df,
		x=x_col,
		y=y_col,
		color=color_col,
		markers=True,
		title=title,
	)
	fig.update_traces(mode="lines+markers+text", texttemplate=text_template, textposition="top center")
	if not show_all_labels:
		for trace in fig.data:
			if not trace.y:
				continue
			trace.text = ["" for _ in trace.y]
			trace.text[-1] = f"{trace.y[-1]}"
			trace.texttemplate = "%{text}"
	fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), legend_title_text="")
	st.plotly_chart(fig, use_container_width=True)


def main() -> None:
	st.set_page_config(page_title="项目版本人力看板", page_icon="📊", layout="wide")
	st.title("项目版本人力数据表与看板")
	st.caption("支持客户/项目/版本类型筛选，按月半年年查看趋势、废弃率与人力对比。")

	if "raw_df" not in st.session_state:
		st.session_state.raw_df = empty_dataframe()
		st.session_state.upload_name = None
		st.session_state.upload_bytes = None

	st.subheader("数据维护方式")
	st.caption("所有图表数据均来自上传的 Excel 文件；未上传文件时，图表数据为空。")
	uploaded = st.file_uploader(
		"上传 Excel 数据文件",
		type=["xlsx", "xls", "csv"],
		key="excel_uploader",
		help="文件需包含列：客户、项目、测试人员、版本、版本类型、开始日期、结束日期、投入人力、是否为废弃版本、废弃版本人力、废弃原因。",
	)
	if uploaded is not None:
		uploaded_data = uploaded.getvalue()
		if uploaded_data != st.session_state.get("upload_bytes"):
			try:
				new_df = read_uploaded_file(uploaded.name, uploaded_data)
			except Exception as exc:
				st.error(f"上传文件读取失败，已保留原数据：{exc}")
			else:
				st.session_state.raw_df = new_df
				st.session_state.upload_name = uploaded.name
				st.session_state.upload_bytes = uploaded_data
				reset_filter_state()
				st.success(f"已加载上传文件：{uploaded.name}，共 {len(new_df)} 行。")
	elif st.session_state.get("upload_bytes") is not None:
		st.session_state.raw_df = empty_dataframe()
		st.session_state.upload_name = None
		st.session_state.upload_bytes = None
		reset_filter_state()
		st.info("已清除上传文件，图表数据为空。")

	source_label = (
		f"已上传文件：{st.session_state.get('upload_name', '')}"
		if st.session_state.get("upload_bytes")
		else "未上传 Excel，图表数据为空"
	)
	st.caption(f"当前数据来源：{source_label}｜共 {len(st.session_state.raw_df)} 行")

	with st.sidebar:
		st.header("筛选条件")
		today = date.today()
		time_mode = st.radio("时间选择方式", ["快捷范围", "自定义范围"], index=0, key="filter_time_mode")

		quick_range = st.selectbox(
			"快捷时间范围",
			["本月", "上月", "最近30天", "最近90天", "今年"],
			index=0,
			disabled=time_mode != "快捷范围",
			key="filter_quick_range",
		)

		if quick_range == "本月":
			month_start = today.replace(day=1)
			default_range = (month_start, month_end(today))
		elif quick_range == "上月":
			this_month_start = today.replace(day=1)
			last_month_end = this_month_start - timedelta(days=1)
			last_month_start = last_month_end.replace(day=1)
			default_range = (last_month_start, last_month_end)
		elif quick_range == "最近30天":
			default_range = (today - timedelta(days=29), today)
		elif quick_range == "最近90天":
			default_range = (today - timedelta(days=89), today)
		elif quick_range == "今年":
			default_range = (date(today.year, 1, 1), today)
		else:
			default_range = (today.replace(day=1), today)

		if time_mode == "快捷范围":
			start_date, end_date = default_range
			st.caption(f"当前快捷范围：{start_date} 到 {end_date}")
		else:
			default_start, default_end = default_range
			start_date = st.date_input("开始日期", value=default_start, key="filter_start_date")
			end_date = st.date_input("结束日期", value=default_end, key="filter_end_date")

		if start_date > end_date:
			start_date, end_date = end_date, start_date

		discard_filter = st.selectbox(
			"版本状态",
			["全部版本", "仅废弃版本", "仅非废弃版本"],
			index=0,
			key="filter_discard",
		)

		customer_options = sorted(
			[
				v
				for v in st.session_state.raw_df["客户"].dropna().astype("string").unique().tolist()
				if str(v).strip()
			]
		)
		selected_customers = st.multiselect(
			"客户筛选",
			options=customer_options,
			default=[],
			help="默认不筛选，显示全部客户；选择后仅显示所选客户。",
			key="filter_customers",
		)

		project_options = sorted(
			[
				project
				for project in st.session_state.raw_df["项目"].dropna().astype("string").unique().tolist()
				if str(project).strip()
			]
		)
		selected_projects = st.multiselect(
			"项目筛选",
			options=project_options,
			default=[],
			help="默认不筛选，显示全部项目；选择后仅显示所选项目。",
			key="filter_projects",
		)

		selected_types = st.multiselect(
			"版本类型筛选",
			options=VERSION_TYPE_OPTIONS,
			default=[],
			help="默认不筛选，显示全部版本类型。",
			key="filter_types",
		)

		tester_options = sorted(
			[
				tester
				for tester in st.session_state.raw_df["测试人员"].dropna().astype("string").unique().tolist()
				if str(tester).strip()
			]
		)
		selected_testers = st.multiselect(
			"测试人员筛选",
			options=tester_options,
			default=[],
			help="默认不筛选，显示全部测试人员；选择后仅显示所选人员。",
			key="filter_testers",
		)

		reason_options = sorted(
			[
				reason
				for reason in st.session_state.raw_df["废弃原因"].dropna().astype("string").unique().tolist()
				if str(reason).strip()
			]
		)
		selected_discard_reasons = st.multiselect(
			"废弃原因筛选",
			options=reason_options,
			default=[],
			help="不选表示不过滤废弃原因。",
			key="filter_reasons",
		)

		version_keyword = st.text_input("版本关键字", value="", placeholder="例如 202607 / mr", key="filter_version_kw")

		st.divider()
		label_mode = st.radio("标签显示", ["全部标签", "仅末端标签"], index=0)
		show_all_labels = label_mode == "全部标签"

	normalized_edited = normalize_dataframe(st.session_state.raw_df)

	filtered = filter_by_date(normalized_edited, start_date, end_date)
	filtered = filter_by_discard_status(filtered, discard_filter)
	filtered = apply_dimension_filters(
		filtered,
		selected_customers,
		selected_projects,
		selected_types,
		selected_discard_reasons,
		version_keyword,
	)
	if selected_testers:
		filtered = filtered[filtered["测试人员"].isin(selected_testers)].copy()
	filtered = add_month_column(filtered)

	st.divider()
	st.subheader("看板")
	st.caption(f"当前范围：{start_date} 到 {end_date}（按结束日期）")

	total_input = float(filtered["投入人力"].sum()) if not filtered.empty else 0.0
	total_discard = float(filtered["废弃版本人力"].sum()) if not filtered.empty else 0.0
	total_versions = int(filtered["版本"].nunique()) if not filtered.empty else 0
	discard_rate = rate_percent(float(filtered["是否为废弃版本"].sum()), float(len(filtered))) if not filtered.empty else 0.0

	m1, m2, m3, m4, m5 = st.columns(5)
	m1.metric("投入人力（合计）", f"{total_input:.1f}")
	m2.metric("废弃人力（合计）", f"{total_discard:.1f}")
	m3.metric("版本数（去重）", f"{total_versions}")
	m4.metric("废弃版本率", f"{discard_rate:.1f}%")
	m5.metric("客户数", f"{filtered['客户'].nunique() if not filtered.empty else 0}")

	if filtered.empty:
		st.info("当前没有可展示的数据：请先在上方上传 Excel 数据文件，或调整筛选条件后重试。")
		return

	st.divider()
	st.subheader("图表导航")
	module_options = [
		"1) 不同项目版本趋势",
		"2) 同客户下不同项目版本对比",
		"3) 废弃版本率（月/年）与废弃原因",
		"4) 单项目总人力（月/年）",
		"5) 不同项目每个月 MR/SMR 版本数量对比",
		"6) MR/SMR 版本数量（类型维度）",
	]
	view_mode = st.radio("展示模式", ["单模块查看", "全部展开"], horizontal=True)
	selected_module = st.selectbox("选择要查看的图表模块", options=module_options, index=0, disabled=view_mode == "全部展开")
	show_all_modules = view_mode == "全部展开"

	if show_all_modules or selected_module == "1) 不同项目版本趋势":
		st.subheader("1) 不同项目版本趋势（按月/半年/年）")
		trend_mode = st.radio("趋势区间", ["月", "半年", "年"], horizontal=True)
		trend_start, trend_end = get_window_range(trend_mode, end_date)
		trend_df = filtered[
			(pd.to_datetime(filtered["结束日期"], errors="coerce").dt.date >= trend_start)
			& (pd.to_datetime(filtered["结束日期"], errors="coerce").dt.date <= trend_end)
		].copy()

		if trend_df.empty:
			st.info("当前趋势区间无数据。")
		else:
			freq = "W-MON" if trend_mode == "月" else "MS"
			type_tabs = st.tabs(["全部", "MR", "SMR", "在研"])
			for tab, type_name in zip(type_tabs, ["全部", "mr", "smr", "在研"]):
				with tab:
					type_df = trend_df if type_name == "全部" else trend_df[trend_df["版本类型"] == type_name]
					if type_df.empty:
						st.caption("该类型在当前区间无数据。")
						continue
					project_trend = (
						type_df.groupby([pd.Grouper(key="结束日期_dt", freq=freq), "项目"], as_index=False)["版本"]
						.count()
						.rename(columns={"版本": "版本数量"})
					)
					project_trend["时间"] = project_trend["结束日期_dt"].dt.strftime("%Y-%m-%d" if trend_mode == "月" else "%Y-%m")
					c1, c2 = st.columns([3, 2])
					with c1:
						render_line_chart(
							project_trend,
							x_col="时间",
							y_col="版本数量",
							color_col="项目",
							text_template="%{y:.0f}",
							show_all_labels=show_all_labels,
						)
					with c2:
						st.dataframe(project_trend[["时间", "项目", "版本数量"]], width="stretch")

	if show_all_modules or selected_module == "2) 同客户下不同项目版本对比":
		st.subheader("2) 同客户下不同项目版本对比")
		compare_customer = st.selectbox("选择客户", options=sorted(filtered["客户"].unique().tolist()))
		customer_df = filtered[filtered["客户"] == compare_customer].copy()
		if customer_df.empty:
			st.info("该客户暂无数据。")
		else:
			customer_compare = (
				customer_df.groupby(["项目", "版本类型"], as_index=False)["版本"]
				.nunique()
				.rename(columns={"版本": "版本数量"})
			)
			c1, c2 = st.columns([3, 2])
			with c1:
				render_bar_chart(customer_compare, x_col="项目", y_col="版本数量", color_col="版本类型", text_template="%{y:.0f}")
			with c2:
				st.dataframe(customer_compare, width="stretch")

	if show_all_modules or selected_module == "3) 废弃版本率（月/年）与废弃原因":
		st.subheader("3) 废弃版本率（月/年）与废弃原因")
		rate_project_options = sorted(filtered["项目"].dropna().astype("string").unique().tolist())
		selected_rate_projects = st.multiselect(
			"废弃分析项目筛选",
			options=rate_project_options,
			default=rate_project_options,
			help="仅影响本模块的废弃率与废弃原因图表。",
		)
		rate_source = filtered[filtered["项目"].isin(selected_rate_projects)].copy() if selected_rate_projects else filtered.iloc[0:0].copy()
		if rate_source.empty:
			st.info("当前废弃分析项目筛选后无数据。")
		else:
			rate_mode = st.radio("废弃率维度", ["按月", "按年"], horizontal=True)
			left_chart, right_chart = st.columns(2)
			if rate_mode == "按月":
				rate_df = (
					rate_source.groupby("结束月份", as_index=False)
					.agg(总版本数=("版本", "nunique"), 废弃版本数=("是否为废弃版本", "sum"))
				)
				rate_df["废弃版本率(%)"] = rate_df.apply(
					lambda row: rate_percent(float(row["废弃版本数"]), float(row["总版本数"])),
					axis=1,
				)
				with left_chart:
					render_line_chart(
						rate_df,
						x_col="结束月份",
						y_col="废弃版本率(%)",
						text_template="%{y:.1f}%",
						show_all_labels=show_all_labels,
					)
			else:
				rate_df = (
					rate_source.groupby("结束年份", as_index=False)
					.agg(总版本数=("版本", "nunique"), 废弃版本数=("是否为废弃版本", "sum"))
				)
				rate_df["结束年份"] = rate_df["结束年份"].astype("string")
				rate_df["废弃版本率(%)"] = rate_df.apply(
					lambda row: rate_percent(float(row["废弃版本数"]), float(row["总版本数"])),
					axis=1,
				)
				with left_chart:
					render_bar_chart(rate_df, x_col="结束年份", y_col="废弃版本率(%)", text_template="%{y:.1f}%")

			discard_reason_df = (
				rate_source[rate_source["是否为废弃版本"]]
				.groupby("废弃原因", as_index=False)["版本"]
				.nunique()
				.rename(columns={"版本": "废弃版本数"})
				.sort_values(by="废弃版本数", ascending=False)
			)
			if discard_reason_df.empty:
				with right_chart:
					st.caption("当前筛选范围内无废弃版本。")
			else:
				with right_chart:
					render_bar_chart(discard_reason_df, x_col="废弃原因", y_col="废弃版本数", text_template="%{y:.0f}")

			rate_table_col, reason_table_col = st.columns(2)
			with rate_table_col:
				st.dataframe(rate_df, width="stretch")
			with reason_table_col:
				if discard_reason_df.empty:
					st.caption("无废弃原因明细。")
				else:
					st.dataframe(discard_reason_df, width="stretch")

	if show_all_modules or selected_module == "4) 单项目总人力（月/年）":
		st.subheader("4) 单项目总人力（月/年）")
		one_project = st.selectbox("选择单项目", options=sorted(filtered["项目"].unique().tolist()))
		project_granularity = st.radio("单项目人力维度", ["按月", "按年"], horizontal=True)
		one_project_df = filtered[filtered["项目"] == one_project].copy()
		if one_project_df.empty:
			st.info("该项目暂无数据。")
		else:
			if project_granularity == "按月":
				human_df = (
					one_project_df.groupby("结束月份", as_index=False)["投入人力"]
					.sum()
					.rename(columns={"结束月份": "时间", "投入人力": "总人力"})
				)
				c1, c2 = st.columns([3, 2])
				with c1:
					render_line_chart(
						human_df,
						x_col="时间",
						y_col="总人力",
						text_template="%{y:.1f}",
						show_all_labels=show_all_labels,
					)
				with c2:
					st.dataframe(human_df, width="stretch")
			else:
				human_df = (
					one_project_df.groupby("结束年份", as_index=False)["投入人力"]
					.sum()
					.rename(columns={"结束年份": "时间", "投入人力": "总人力"})
				)
				human_df["时间"] = human_df["时间"].astype("string")
				c1, c2 = st.columns([3, 2])
				with c1:
					render_bar_chart(human_df, x_col="时间", y_col="总人力", text_template="%{y:.1f}")
				with c2:
					st.dataframe(human_df, width="stretch")

	if show_all_modules or selected_module == "5) 不同项目每个月 MR/SMR 版本数量对比":
		st.subheader("5) 不同项目每个月 MR/SMR 版本数量对比（按年按月筛选）")
		year_options = sorted([int(y) for y in filtered["结束年份"].dropna().unique().tolist()])
		selected_year = st.selectbox("年份", options=year_options, index=len(year_options) - 1)
		selected_month_label = st.selectbox("月份", options=["全年"] + [f"{i:02d}" for i in range(1, 13)], index=0)

		mr_smr = filtered[
			(filtered["结束年份"] == selected_year)
			& (filtered["版本类型"].isin(["mr", "smr"]))
		].copy()

		if selected_month_label != "全年":
			mr_smr = mr_smr[pd.to_datetime(mr_smr["结束日期_dt"]).dt.month == int(selected_month_label)]

		if mr_smr.empty:
			st.info("当前年/月筛选下没有 MR/SMR 数据。")
		else:
			if selected_month_label == "全年":
				monthly_compare = (
					mr_smr.groupby(["结束月份", "项目", "版本类型"], as_index=False)["版本"]
					.nunique()
					.rename(columns={"版本": "版本数量"})
				)
				monthly_compare["项目-类型"] = monthly_compare["项目"] + "-" + monthly_compare["版本类型"].str.upper()
				c1, c2 = st.columns([3, 2])
				with c1:
					render_line_chart(
						monthly_compare,
						x_col="结束月份",
						y_col="版本数量",
						color_col="项目-类型",
						text_template="%{y:.0f}",
						show_all_labels=show_all_labels,
					)
				with c2:
					st.dataframe(monthly_compare[["结束月份", "项目", "版本类型", "版本数量"]], width="stretch")
			else:
				month_compare = (
					mr_smr.groupby(["项目", "版本类型"], as_index=False)["版本"]
					.nunique()
					.rename(columns={"版本": "版本数量"})
				)
				c1, c2 = st.columns([3, 2])
				with c1:
					render_bar_chart(month_compare, x_col="项目", y_col="版本数量", color_col="版本类型", text_template="%{y:.0f}")
				with c2:
					st.dataframe(month_compare, width="stretch")

	if show_all_modules or selected_module == "6) MR/SMR 版本数量（类型维度）":
		st.subheader("6) MR/SMR 版本数量（类型维度）")
		mr_smr_view = filtered[filtered["版本类型"].isin(["mr", "smr"])].copy()
		if mr_smr_view.empty:
			st.caption("当前筛选范围内无 MR/SMR 数据。")
		else:
			f1, f2, f3 = st.columns(3)
			with f1:
				matrix_year_options = sorted([int(y) for y in mr_smr_view["结束年份"].dropna().unique().tolist()])
				matrix_year = st.selectbox("汇总年份", options=matrix_year_options, index=len(matrix_year_options) - 1)
			with f2:
				matrix_month = st.selectbox("汇总月份", options=["全年"] + [f"{i:02d}" for i in range(1, 13)], index=0)
			with f3:
				matrix_projects = sorted(mr_smr_view["项目"].astype("string").unique().tolist())
				matrix_project = st.selectbox("汇总项目", options=["全部项目"] + matrix_projects, index=0)

			matrix_filtered = mr_smr_view[mr_smr_view["结束年份"] == matrix_year].copy()
			if matrix_month != "全年":
				matrix_filtered = matrix_filtered[
					pd.to_datetime(matrix_filtered["结束日期_dt"]).dt.month == int(matrix_month)
				]
			if matrix_project != "全部项目":
				matrix_filtered = matrix_filtered[matrix_filtered["项目"] == matrix_project]

			if matrix_filtered.empty:
				st.caption("当前汇总筛选条件下无 MR/SMR 数据。")
			else:
				type_count_df = (
					matrix_filtered.groupby("版本类型", as_index=False)["版本"]
					.nunique()
					.rename(columns={"版本": "版本数量"})
				)
				type_count_df["版本类型"] = pd.Categorical(type_count_df["版本类型"], categories=["mr", "smr"], ordered=True)
				type_count_df = type_count_df.sort_values(by="版本类型")

				c1, c2 = st.columns([3, 2])
				with c1:
					render_bar_chart(type_count_df, x_col="版本类型", y_col="版本数量", text_template="%{y:.0f}")
				with c2:
					project_split_df = (
						matrix_filtered.groupby(["项目", "版本类型"], as_index=False)["版本"]
						.nunique()
						.rename(columns={"版本": "版本数量"})
					)
					st.dataframe(project_split_df, width="stretch")

if __name__ == "__main__":
	main()
