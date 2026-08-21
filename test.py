from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import random
import sys

import pandas as pd
import plotly.express as px
import streamlit as st


APP_BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DATA_FILE = APP_BASE_DIR / "manpower_data.csv"

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
DISCARD_REASON_OPTIONS = ["", "需求变更", "质量问题", "资源冲突", "客户取消", "重复版本", "其他"]


def month_start(day: date) -> date:
	return day.replace(day=1)


def month_end(day: date) -> date:
	next_month = day.replace(day=28) + timedelta(days=4)
	return next_month - timedelta(days=next_month.day)


def generate_simulated_rows(base_df: pd.DataFrame, months: int = 24, seed: int = 42) -> list[dict[str, object]]:
	rng = random.Random(seed)
	today = date.today()
	start_month = month_start(today) - timedelta(days=30 * (months - 1))
	start_month = month_start(start_month)
	testers = ["张敏", "李楠", "王强", "周颖", "陈涛", "赵雪"]

	customer_project_map = {
		"华东客户": ["A项目", "A项目增强", "中台重构"],
		"华南客户": ["B项目", "支付升级", "数据治理"],
		"海外客户": ["C项目", "C项目插件", "边缘计算"],
		"政企客户": ["D项目", "安全合规", "运维平台"],
	}

	rows: list[dict[str, object]] = []
	existing_versions = set(base_df["版本"].astype("string").fillna("").tolist()) if not base_df.empty else set()

	for month_idx in range(months):
		current_month_start = month_start(start_month + timedelta(days=31 * month_idx))
		current_month_end = month_end(current_month_start)

		for customer, projects in customer_project_map.items():
			for project in projects:
				mr_count = rng.randint(0, 3)
				smr_count = rng.randint(0, 2)
				in_progress_count = rng.randint(0, 2)

				for vtype, count in [("mr", mr_count), ("smr", smr_count), ("在研", in_progress_count)]:
					for idx in range(1, count + 1):
						version_name = f"{project[:2]}-{current_month_start:%Y%m}-{vtype}-{idx}"
						if version_name in existing_versions:
							continue
						existing_versions.add(version_name)

						start_offset = rng.randint(0, 18)
						end_offset = start_offset + rng.randint(5, 25)
						start_day = current_month_start + timedelta(days=start_offset)
						end_day = min(current_month_end, current_month_start + timedelta(days=end_offset))

						input_manpower = round(rng.uniform(1.5, 12.0), 1)
						is_discard = vtype != "在研" and rng.random() < 0.22
						discard_manpower = round(input_manpower * rng.uniform(0.3, 1.0), 1) if is_discard else 0.0
						discard_reason = rng.choice(DISCARD_REASON_OPTIONS[1:]) if is_discard else ""

						rows.append(
							{
								"客户": customer,
								"项目": project,
								"测试人员": rng.choice(testers),
								"版本": version_name,
								"版本类型": vtype,
								"开始日期": start_day,
								"结束日期": end_day,
								"投入人力": input_manpower,
								"是否为废弃版本": is_discard,
								"废弃版本人力": discard_manpower,
								"废弃原因": discard_reason,
							}
						)

	return rows


def ensure_demo_coverage(df: pd.DataFrame) -> pd.DataFrame:
	if df.empty:
		base = pd.DataFrame(default_rows(), columns=COLUMNS)
		return normalize_dataframe(base)

	temp = df.copy()
	temp_end = pd.to_datetime(temp["结束日期"], errors="coerce")
	month_span = 0
	if temp_end.notna().any():
		month_span = (temp_end.max().year - temp_end.min().year) * 12 + (temp_end.max().month - temp_end.min().month) + 1

	if len(temp) >= 140 and month_span >= 12 and temp["项目"].nunique() >= 4 and temp["客户"].nunique() >= 3:
		return temp

	append_rows = generate_simulated_rows(temp, months=24, seed=2026)
	if not append_rows:
		return temp

	merged = pd.concat([temp, pd.DataFrame(append_rows)], ignore_index=True)
	return normalize_dataframe(merged)


def default_rows() -> list[dict[str, object]]:
	today = date.today()
	return [
		{
			"客户": "华东客户",
			"项目": "A项目",
			"测试人员": "张敏",
			"版本": "A-202607-mr-1",
			"版本类型": "mr",
			"开始日期": today - timedelta(days=45),
			"结束日期": today - timedelta(days=15),
			"投入人力": 6.0,
			"是否为废弃版本": False,
			"废弃版本人力": 0.0,
			"废弃原因": "",
		},
		{
			"客户": "华东客户",
			"项目": "A项目",
			"测试人员": "李楠",
			"版本": "A-202607-smr-1",
			"版本类型": "smr",
			"开始日期": today - timedelta(days=20),
			"结束日期": today - timedelta(days=1),
			"投入人力": 4.0,
			"是否为废弃版本": True,
			"废弃版本人力": 4.0,
			"废弃原因": "需求变更",
		},
		{
			"客户": "华南客户",
			"项目": "B项目",
			"测试人员": "王强",
			"版本": "B-202607-在研-1",
			"版本类型": "在研",
			"开始日期": today - timedelta(days=35),
			"结束日期": today - timedelta(days=5),
			"投入人力": 8.0,
			"是否为废弃版本": False,
			"废弃版本人力": 0.0,
			"废弃原因": "",
		},
	]


def default_dataframe() -> pd.DataFrame:
	base = pd.DataFrame(default_rows(), columns=COLUMNS)
	merged = pd.concat([base, pd.DataFrame(generate_simulated_rows(base, months=24, seed=2025))], ignore_index=True)
	return normalize_dataframe(merged)


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

	normalized["是否为废弃版本"] = normalized["是否为废弃版本"].apply(to_bool)
	normalized.loc[~normalized["是否为废弃版本"], "废弃版本人力"] = 0.0
	normalized.loc[~normalized["是否为废弃版本"], "废弃原因"] = ""
	normalized.loc[
		normalized["是否为废弃版本"] & (normalized["废弃原因"].str.strip() == ""),
		"废弃原因",
	] = "其他"

	normalized = normalized[COLUMNS]
	return normalized


def load_data() -> pd.DataFrame:
	if DATA_FILE.exists():
		loaded = pd.read_csv(DATA_FILE)
		normalized = normalize_dataframe(loaded)
		return ensure_demo_coverage(normalized)
	return ensure_demo_coverage(default_dataframe())


def save_data(df: pd.DataFrame) -> None:
	to_save = df.copy()
	to_save["开始日期"] = pd.to_datetime(to_save["开始日期"], errors="coerce").dt.strftime("%Y-%m-%d")
	to_save["结束日期"] = pd.to_datetime(to_save["结束日期"], errors="coerce").dt.strftime("%Y-%m-%d")
	to_save.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")


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
	header_left, header_right = st.columns([8, 1])
	with header_left:
		st.title("项目版本人力数据表与看板")
		st.caption("支持客户/项目/版本类型筛选，按月半年年查看趋势、废弃率与人力对比。")
	with header_right:
		if st.button("刷新", width="stretch"):
			st.session_state.raw_df = load_data()
			st.rerun()

	if "raw_df" not in st.session_state:
		st.session_state.raw_df = load_data()

	with st.sidebar:
		st.header("筛选条件")
		today = date.today()
		time_mode = st.radio("时间选择方式", ["快捷范围", "自定义范围"], index=0)

		quick_range = st.selectbox(
			"快捷时间范围",
			["本月", "上月", "最近30天", "最近90天", "今年"],
			index=0,
			disabled=time_mode != "快捷范围",
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
			selected_range = st.date_input(
				"结束日期范围",
				value=default_range,
				help="统计仅包含结束日期在该范围内的版本记录。",
			)

			if isinstance(selected_range, tuple) and len(selected_range) == 2:
				start_date, end_date = selected_range
			else:
				start_date, end_date = default_range

		if start_date > end_date:
			start_date, end_date = end_date, start_date

		discard_filter = st.selectbox(
			"版本状态",
			["全部版本", "仅废弃版本", "仅非废弃版本"],
			index=0,
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
			default=customer_options,
			help="可按客户横向对比不同项目版本。",
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
			default=project_options,
			help="不选择即显示全部项目。",
		)

		selected_types = st.multiselect(
			"版本类型筛选",
			options=VERSION_TYPE_OPTIONS,
			default=VERSION_TYPE_OPTIONS,
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
			default=tester_options,
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
		)

		version_keyword = st.text_input("版本关键字", value="", placeholder="例如 202607 / mr")

		if st.button("追加模拟数据（24个月）", width="stretch"):
			sim_df = pd.DataFrame(generate_simulated_rows(st.session_state.raw_df, months=24, seed=random.randint(1, 999999)))
			if not sim_df.empty:
				st.session_state.raw_df = normalize_dataframe(
					pd.concat([st.session_state.raw_df, sim_df], ignore_index=True)
				)
				st.success(f"已追加模拟数据 {len(sim_df)} 条，可点击保存写入CSV。")
				st.rerun()

		st.divider()
		label_mode = st.radio("标签显示", ["全部标签", "仅末端标签"], index=0)
		show_all_labels = label_mode == "全部标签"

	st.subheader("数据维护方式")
	st.info("页面内数据表编辑区已移除。请直接在 Excel 中维护 manpower_data.csv，再点击页面右上角“刷新”加载最新数据。")

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
		st.info("当前时间范围内没有数据，请调整筛选条件或录入数据。")
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
