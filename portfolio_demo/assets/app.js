"use strict";

const state = {
  view: "overview",
  selectedId: "demo-101",
  strategy: "interior_refresh",
  marketFilter: "all",
  search: "",
  scopeOverrides: {},
  financialInputs: {},
  timingInputs: {lease_up_months: 1, monthly_carry_cost: 350},
  analysis: null,
  busy: false,
};
let demo;

const $ = (selector, root=document) => root.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const money = value => value == null ? "Not available" : new Intl.NumberFormat("en-US", {style:"currency",currency:"USD",maximumFractionDigits:0}).format(value);
const money2 = value => value == null ? "Not available" : new Intl.NumberFormat("en-US", {style:"currency",currency:"USD",maximumFractionDigits:2}).format(value);
const percent = value => value == null ? "Not available" : `${(Number(value)*100).toFixed(1)}%`;
const number = value => new Intl.NumberFormat("en-US").format(Number(value)||0);
const title = value => ({overview:"Overview",markets:"Markets",properties:"Properties",property:"Property workspace",scope:"Renovation scope",financials:"Financials",scenarios:"Scenarios",report:"Acquisition report"}[value] || "Overview");
const selectedProperty = () => demo.properties.find(item => item.id === state.selectedId) || demo.properties[0];
const selectedMarket = () => demo.markets.find(item => item.id === selectedProperty().market_id);

async function init(){
  try {
    const response = await fetch("/api/bootstrap", {cache:"no-store"});
    if (!response.ok) throw new Error("The local demo data could not be loaded.");
    demo = await response.json();
    const requestedView = new URLSearchParams(window.location.search).get("view");
    if (VIEWS[requestedView]) state.view = requestedView;
    $("#propertyCount").textContent = demo.properties.length;
    $("#footerProjectCount").textContent = demo.project_count;
    await runAnalysis(false);
    render();
  } catch (error) {
    $("#main").innerHTML = `<section class="panel empty-state"><strong>Demo did not start</strong>${esc(error.message)}<p>Restart the local demo using the README instructions.</p></section>`;
  }
}

function payload(){
  return {property_id:state.selectedId,strategy:state.strategy,scope_overrides:state.scopeOverrides,financial_inputs:state.financialInputs,timing_inputs:state.timingInputs};
}

async function runAnalysis(showToast=true){
  state.busy = true;
  try {
    const response = await fetch("/api/analyze", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload())});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Analysis could not be calculated.");
    state.analysis = data;
    if (showToast) toast("Scenario recalculated from fictional inputs.");
  } catch (error) {
    toast(error.message);
  } finally { state.busy = false; }
}

function toast(message){
  const item=document.createElement("div");item.className="toast";item.setAttribute("role","status");item.textContent=message;document.body.append(item);setTimeout(()=>item.remove(),2700);
}

function intro(eyebrow, heading, subtitle, actions=""){
  return `<div class="page-title-row"><div><div class="eyebrow">${eyebrow}</div><h1 class="page-title">${heading}</h1><p class="page-subtitle">${subtitle}</p></div><div class="button-row">${actions}</div></div>`;
}

function metric(label,value,note,icon="◌"){
  return `<article class="card metric-card"><div class="metric-top"><span>${label}</span><span class="metric-icon" aria-hidden="true">${icon}</span></div><div class="metric-value">${value}</div><div class="metric-note">${note}</div></article>`;
}

function chartSvg(){
  const values=demo.markets.map(m=>m.median_rent);
  const x=[42,170,298], y=values.map(v=>185-(v-1100)/5.5);
  const points=x.map((v,i)=>`${v},${y[i].toFixed(1)}`).join(" ");
  const area=`${x[0]},205 ${points} ${x[2]},205`;
  return `<svg viewBox="0 0 340 230" role="img" aria-label="Fictional median rent comparison across three demo markets"><defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#8cbaca" stop-opacity=".25"/><stop offset="1" stop-color="#8cbaca" stop-opacity=".02"/></linearGradient></defs><line x1="32" y1="44" x2="326" y2="44" class="chart-grid"/><line x1="32" y1="94" x2="326" y2="94" class="chart-grid"/><line x1="32" y1="144" x2="326" y2="144" class="chart-grid"/><line x1="32" y1="194" x2="326" y2="194" class="chart-grid"/><text x="0" y="47" class="chart-axis">$1.8k</text><text x="0" y="97" class="chart-axis">$1.6k</text><text x="0" y="147" class="chart-axis">$1.4k</text><text x="0" y="197" class="chart-axis">$1.2k</text><polygon points="${area}" class="chart-area"/><polyline points="${points}" class="chart-line"/>${x.map((cx,i)=>`<circle cx="${cx}" cy="${y[i]}" r="4" class="chart-point"/><text x="${cx}" y="222" class="chart-axis" text-anchor="middle">${esc(demo.markets[i].name)}</text>`).join("")}</svg>`;
}

function marketMini(m){
  return `<div class="market-mini"><div><strong><i class="market-dot"></i>${esc(m.name)}</strong><small>${m.property_count} fictional listings · ${m.days_on_market} simulated days on market</small></div><div><div class="market-price">${money(m.median_price)}</div><div class="market-rent">${money(m.median_rent)}/mo rent reference</div></div></div>`;
}

function propertyCard(p){
  const market=demo.markets.find(m=>m.id===p.market_id);
  return `<article class="property-card"><div class="property-card-top"><span class="eyebrow">${esc(market?.name || "Demo market")}</span><span class="status-chip ${p.condition.includes("Inspection")?"warn":"blue"}">${esc(p.listing_status.replace("Simulated ",""))}</span></div><h3>${esc(p.label)}</h3><p>Parcel ${esc(p.parcel)} · fictional sample</p><div class="property-card-metrics"><div><span>Asking assumption</span><strong>${money(p.asking_price)}</strong></div><div><span>Rent assumption</span><strong>${money(p.monthly_rent)}/mo</strong></div><div><span>Home facts</span><strong>${p.beds} bd · ${p.baths} ba</strong></div><div><span>Living area</span><strong>${number(p.sqft)} sqft</strong></div></div><button class="btn small" data-open-property="${esc(p.id)}">Open workspace <span aria-hidden="true">→</span></button></article>`;
}

function renderOverview(){
  const medianPrice=Math.round(demo.markets.reduce((s,m)=>s+m.median_price,0)/demo.markets.length);
  const medianRent=Math.round(demo.markets.reduce((s,m)=>s+m.median_rent,0)/demo.markets.length);
  const p=selectedProperty(), a=state.analysis;
  return `${intro("PORTFOLIO OVERVIEW","Research a market. Screen a property.","Browse sample markets, review a property, and test an underwriting scenario. All figures are fictional.",`<button class="btn primary" data-view="properties">Browse demo properties <span aria-hidden="true">→</span></button>`)}
    <div class="grid metrics">${metric("Demo markets",demo.markets.length,"Fictional neighborhood profiles","⌖")}${metric("Sample properties",demo.properties.length,"Searchable listing fixtures","⌂")}${metric("Mean market price input",money(medianPrice),"Average of sample market medians","↗")}${metric("Mean rent input",`${money(medianRent)}<small>/mo</small>`,`Average of sample rent medians · not achieved rent`,"⌑")}</div>
    <div class="dashboard-columns"><section class="panel"><div class="panel-heading"><div><h2>Neighborhood rent snapshots</h2><p>Fictional monthly rent examples</p></div><button class="text-link" data-view="markets">Compare markets →</button></div><div class="chart-box">${chartSvg()}</div><div class="chart-legend"><span><i class="legend-dot"></i>Sample rent assumptions</span><span>Not rent history or a forecast</span></div></section>
      <section class="panel"><div class="panel-heading"><div><h2>Market quick compare</h2><p>Choose an area to explore the sample inventory</p></div></div><div class="market-mini-list">${demo.markets.map(marketMini).join("")}</div></section></div>
    <section class="panel"><div class="panel-heading"><div><h2>Continue with a property</h2><p>Current selection · ${esc(p.label)} · costs are calculated from the fictional reference records below.</p></div><button class="btn small" data-view="property">Open selected property</button></div><div class="mini-stats"><div class="mini-stat"><span>Comparable sale median</span><strong>${money(a?.value_reference.median_comparable_sale)}</strong></div><div class="mini-stat"><span>Preliminary scope</span><strong>${money(a?.scope.total)}</strong></div><div class="mini-stat"><span>Monthly cash flow scenario</span><strong>${money(a?.finance.metrics.monthly_cash_flow)}</strong></div></div></section>
    <section class="panel"><div class="panel-heading"><div><h2>Featured demo properties</h2><p>Fictional examples showing different workflows.</p></div><button class="text-link" data-view="properties">View all ${demo.properties.length} →</button></div><div class="property-cards">${demo.properties.slice(0,3).map(propertyCard).join("")}</div></section>`;
}

function renderMarkets(){
  const maxPrice=Math.max(...demo.markets.map(m=>m.median_price));
  const rows=demo.markets.map(m=>`<tr><td><strong>${esc(m.name)}</strong><br><span class="scope-method">${esc(m.profile)}</span></td><td>${money(m.median_price)}</td><td>${money(m.median_rent)}/mo</td><td>${percent(m.vacancy_rate)}</td><td>${m.days_on_market}</td><td>${m.inventory_months.toFixed(1)} mo</td><td><span class="trend">+${percent(m.trend)}</span></td><td><button class="btn small" data-filter-market="${esc(m.id)}">Browse area</button></td></tr>`).join("");
  const bars=demo.markets.map(m=>`<div class="scenario-bar-row"><span>${esc(m.name)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.round(m.median_price/maxPrice*100)}%"></div></div><span class="scenario-figure">${money(m.median_price)}</span></div>`).join("");
  return `${intro("MARKET RESEARCH","Compare the demo markets","Compare three fictional markets. These figures do not describe real neighborhoods.",`<button class="btn primary" data-view="properties">Find properties</button>`)}<div class="section-split"><section class="panel"><div class="panel-heading"><div><h2>Market snapshot</h2><p>Fictional sample values</p></div><span class="evidence-stamp">SIMULATED</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Area</th><th>Median price</th><th>Rent reference</th><th>Vacancy assumption</th><th>Days on market</th><th>Inventory</th><th>Illustrative trend</th><th></th></tr></thead><tbody>${rows}</tbody></table></div></section><section class="panel"><div class="panel-heading"><div><h2>Relative asking price</h2><p>Bars compare the three fictional market assumptions</p></div></div><div class="scenario-bars">${bars}</div><div class="support-note"><span>i</span><div><strong>Not a forecast.</strong> This sample trend is not a prediction or a measured market result.</div></div></section></div><section class="panel"><div class="panel-heading"><div><h2>How to use this page</h2><p>Choose an area, review a sample property, then test a scenario.</p></div></div><div class="mini-stats"><div class="mini-stat"><span>01 · Choose an area</span><strong>Compare indicators</strong></div><div class="mini-stat"><span>02 · Inspect a listing</span><strong>Review comps &amp; facts</strong></div><div class="mini-stat"><span>03 · Model a scenario</span><strong>Scope → returns → report</strong></div></div></section>`;
}

function renderProperties(){
  const options=[`<option value="all">All demo markets</option>`,...demo.markets.map(m=>`<option value="${esc(m.id)}" ${state.marketFilter===m.id?"selected":""}>${esc(m.name)}</option>`)].join("");
  return `${intro("PROPERTY DISCOVERY","Browse fictional listings","Search the demonstration inventory and open a property workspace. Listing status and pricing are simulated inputs.",`<button class="btn soft" data-view="markets">← Compare markets</button>`)}<section class="panel"><div class="search-toolbar"><input class="search-input" id="propertySearch" type="search" placeholder="Search sample property or parcel" value="${esc(state.search)}" aria-label="Search sample properties"><select class="select-input" id="marketFilter" aria-label="Filter demo market">${options}</select><span class="evidence-stamp">${demo.properties.length} FIXTURES</span></div><div id="propertyResults" class="property-cards">${visibleProperties().map(propertyCard).join("") || `<div class="empty-state"><strong>No sample properties match</strong>Clear the search or choose another demo market.</div>`}</div></section><p class="page-subtitle">No external listing search runs in this portfolio app. Property labels and parcel IDs are made-up examples.</p>`;
}

function visibleProperties(){
  const query=state.search.trim().toLowerCase();
  return demo.properties.filter(p=>(state.marketFilter==="all"||p.market_id===state.marketFilter)&&(!query||`${p.label} ${p.parcel} ${p.property_type}`.toLowerCase().includes(query)));
}

function compTable(rows,kind){
  const sales=kind==="sales";
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Fictional comparable</th><th>${sales?"Sale price":"Rent ask"}</th><th>Area</th><th>Bedrooms</th><th>Distance</th><th>Evidence label</th></tr></thead><tbody>${rows.map(c=>`<tr><td><strong>${esc(c.label)}</strong><br><span class="scope-method">${sales?esc(c.sale_month):"Synthetic fixture"}</span></td><td>${money(sales?c.sale_price:c.monthly_rent)}${sales?"":"/mo"}</td><td>${number(c.sqft)} sqft</td><td>${c.beds}</td><td>${c.distance_mi.toFixed(1)} mi</td><td><span class="table-tag">${sales?"SIMULATED CLOSED":"SIMULATED ASKING"}</span></td></tr>`).join("")}</tbody></table></div>`;
}

function propertyFacts(p){
  return `<div class="fact-strip"><span class="fact-pill"><strong>${p.beds}/${p.baths}</strong> beds/baths</span><span class="fact-pill"><strong>${number(p.sqft)}</strong> sqft</span><span class="fact-pill"><strong>${p.year_built}</strong> built</span><span class="fact-pill"><strong>${p.basement?`${number(p.basement_sqft)} sqft`:"No"}</strong> basement</span><span class="fact-pill"><strong>${esc(p.garage)}</strong></span><span class="fact-pill"><strong>${esc(p.property_type)}</strong></span></div>`;
}

function renderProperty(){
  const p=selectedProperty(),a=state.analysis,m=selectedMarket();
  return `${intro("PROPERTY WORKSPACE",esc(p.label),`Parcel ${esc(p.parcel)} · ${esc(m.name)} demo market · saved only in this browser session`, `<button class="btn primary" data-view="scope">Build renovation scope →</button>`)}
    <div class="split-hero"><section class="property-hero"><span class="evidence-stamp">SIMULATED PROPERTY</span><h2>${esc(p.label)}</h2><p>${esc(p.description)}</p>${propertyFacts(p)}</section><section class="panel"><div class="panel-heading"><div><h2>At-a-glance screen</h2><p>References from simulated comparable fixtures</p></div></div><div class="evidence-list"><div class="evidence-row"><strong>Asking price</strong><span>${money(p.asking_price)} · simulated</span></div><div class="evidence-row"><strong>Sale comp median</strong><span>${money(a.value_reference.median_comparable_sale)} · ${a.value_reference.sale_count} records</span></div><div class="evidence-row"><strong>Rent comp median</strong><span>${money(a.rent_reference.median_comparable_asking_rent)}/mo · asking only</span></div><div class="evidence-row"><strong>Current condition</strong><span>${esc(p.condition)} · no inspection</span></div><div class="evidence-row"><strong>Market</strong><span>${esc(m.name)} · fictional</span></div></div></section></div>
    <section class="panel"><div class="panel-heading"><div><h2>Property facts &amp; evidence</h2><p>Every record has a synthetic source label; no fact is verified.</p></div><span class="evidence-stamp">SOURCE REVIEW</span></div><div class="evidence-list"><div class="evidence-row"><strong>Property profile</strong><span>SIMULATED FIXTURE · bedrooms, area, year, basement, parking</span></div><div class="evidence-row"><strong>Listing observation</strong><span>${esc(p.listing_status)} · not a live listing</span></div><div class="evidence-row"><strong>Tax and insurance</strong><span>Scenario inputs · ${money(p.annual_tax)} tax / ${money(p.annual_insurance)} insurance per year</span></div><div class="evidence-row"><strong>Sales &amp; rents</strong><span>Three made-up records in each cohort</span></div><div class="evidence-row"><strong>Inspection / permits</strong><span>Not supplied · further review required</span></div></div></section>
    <section class="panel"><div class="panel-heading"><div><h2>Comparable sales</h2><p>Illustrative closed-sale examples · not independently sourced</p></div><span class="table-tag">MEDIAN ${money(a.value_reference.median_comparable_sale)}</span></div>${compTable(a.sales,"sales")}</section>
    <section class="panel"><div class="panel-heading"><div><h2>Rental references</h2><p>Asking-rent examples · not achieved or approved rent</p></div><span class="table-tag">MEDIAN ${money(a.rent_reference.median_comparable_asking_rent)}/MO</span></div>${compTable(a.rentals,"rentals")}</section>
    <div class="button-row"><button class="btn primary" data-view="scope">Continue to renovation scope</button><button class="btn" data-view="financials">Review financial assumptions</button></div>`;
}

function renderScope(){
  const a=state.analysis,p=selectedProperty(),s=a.scope;
  const strategyOptions=[["interior_refresh","Interior refresh · basement stays unfinished"],["finished_basement","Interior refresh + finish basement"],["systems_refresh","Interior refresh + roof and electrical allowances"]].map(([v,l])=>`<option value="${v}" ${state.strategy===v?"selected":""}>${l}</option>`).join("");
  const lines=s.lines.map(line=>`<tr><td><span class="scope-name">${esc(line.label)}</span><span class="scope-method">${esc(line.method)}</span></td><td>${money(line.low)} – ${money(line.high)}</td><td>${line.supporting_projects} / ${line.total_analogs}</td><td><span class="table-tag">SCENARIO ONLY</span></td><td><input class="editable-cost" type="number" min="0" max="10000000" step="100" data-scope-cost="${esc(line.category)}" value="${Number(line.base)}" aria-label="Editable ${esc(line.label)} amount"></td></tr>`).join("");
  return `${intro("RENOVATION ANALYSIS","Draft an itemized scope","A transparent analog-based estimate using only the six fictional reference projects shipped with this demo.",`<button class="btn" data-view="property">← Property facts</button><button class="btn primary" data-view="financials">Continue to financials →</button>`)}
    <section class="panel"><div class="support-note"><span>i</span><div><strong>Preliminary scenario estimate.</strong> This is not an inspection, contractor quote, completed-cost record, or property-specific construction recommendation. Obtain professional review before relying on a real budget.</div></div>
      <div class="scope-toolbar"><label for="strategySelect">Strategy</label><select id="strategySelect" class="select-input">${strategyOptions}</select><span class="scope-total"><small>Current lender-style draft total · estimate only</small><strong id="scopeTotal">${money(s.total)}</strong></span><button class="btn primary" id="recalculateScope" ${state.busy?"disabled":""}>Recalculate scope</button></div>
      <div class="panel-heading"><div><h2>${esc(p.label)} · recommended work packages</h2><p>${s.analog_count} nearest fictional analogs · line amounts can be edited for the scenario</p></div><span class="evidence-stamp">CONTRACTOR REVIEW REQUIRED</span></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Work package &amp; method</th><th>Observed analog range</th><th>Synthetic analogs</th><th>Evidence</th><th>Editable estimate</th></tr></thead><tbody>${lines}</tbody></table></div>
      <div class="button-row" style="margin-top:14px"><button class="btn soft" id="applyScopeEdits">Apply edited amounts</button><button class="btn" id="resetScopeEdits">Reset to analog estimate</button></div>
      <div class="support-note"><span>◎</span><div><strong>How the estimate is formed:</strong> rank the synthetic project records with market (30%), property type (15%), era (15%), living area (25%) and basement (15%); calculate a similarity-weighted mean for each selected category. Area-priced lines multiply the synthetic rate by the subject's stated area. Low/high show the minimum and maximum in the selected fictional analogs; they are not confidence bounds.<br><br><strong>Closest examples:</strong> ${s.analogs.map(x=>`${esc(x.id)} (${x.score}/100)`).join(" · ")}</div></div>
    </section><section class="panel"><div class="panel-heading"><div><h2>Model audit</h2><p>Calculation provenance for this generated scenario</p></div></div><div class="mini-stats"><div class="mini-stat"><span>Method version</span><strong>synthetic-analog-demo-v1</strong></div><div class="mini-stat"><span>Fictional cost records</span><strong>${demo.project_count}</strong></div><div class="mini-stat"><span>Property-specific condition</span><strong>Not established</strong></div></div></section>`;
}

const FINANCE_FIELDS=[
  ["purchase_price","Acquisition price","$",0], ["monthly_rent","Monthly rent assumption","$ / month",0],
  ["vacancy_rate","Vacancy assumption","fraction · 0 to 1",3], ["annual_tax","Annual property tax","$ / year",0],
  ["annual_insurance","Annual insurance","$ / year",0], ["maintenance_rate","Maintenance reserve","fraction · 0 to 1",2],
  ["management_rate","Management expense","fraction · 0 to 1",2], ["other_monthly_expenses","Other expenses","$ / month",0],
  ["ltv","Loan-to-value","fraction · 0 to 1",2], ["interest_rate","Interest rate","fraction · 0 to 1",3],
  ["loan_term_years","Loan term","years",0], ["closing_rate","Closing cost assumption","fraction · 0 to 1",2],
  ["initial_reserves","Initial reserves","$",0]
];
function financeField([key,label,unit,digits],values){
  const val=state.financialInputs[key] ?? values[key];
  const step=digits?0.001:1;
  return `<div class="field"><label for="fin-${key}">${label}</label><input id="fin-${key}" name="${key}" type="number" min="0" max="${digits?1:10000000}" step="${step}" value="${Number(val).toFixed(digits)}" required><small>${unit}</small></div>`;
}

function resultCards(fin){
  const m=fin.metrics;
  return `<div class="result-grid">${[["Estimated NOI",money(m.estimated_noi),"Annual, before debt"],["Monthly cash flow",money(m.monthly_cash_flow),"After modeled debt service"],["DSCR",m.dscr==null?"Not available":`${m.dscr.toFixed(2)}×`,"Scenario ratio"],["Cash-on-cash",percent(m.cash_on_cash),"Stabilized annualized scenario"],["Project uses",money(m.project_uses),"Purchase + rehab + closing + reserves"],["Cash invested",money(m.cash_invested),"Uses after modeled loan proceeds"]].map(([l,v,n])=>`<article class="result-card"><span>${l}</span><strong>${v}</strong><small>${n}</small></article>`).join("")}</div>`;
}

function projectUsesTable(fin){
  const c=fin.metrics.project_uses_components;
  const rows=[["Acquisition price",c.purchase_price,"Employee-entered assumption"],["Preliminary renovation scope",c.rehab_budget,"Selected synthetic scope total"],["Closing costs",c.closing_costs,`${percent(fin.inputs.closing_rate)} × acquisition price`],["Initial reserves",c.initial_reserves,"Employee-entered reserve assumption"]];
  const total=rows.reduce((sum,row)=>sum+row[1],0);
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Project-use component</th><th>Scenario basis</th><th>Amount</th></tr></thead><tbody>${rows.map(([label,value,basis])=>`<tr><td>${label}</td><td>${basis}</td><td>${money(value)}</td></tr>`).join("")}<tr><td><strong>Total project uses</strong></td><td>Sum of four components</td><td><strong>${money(total)}</strong></td></tr></tbody></table></div>`;
}

function renderFinancials(){
  const a=state.analysis,p=selectedProperty(),fin=a.finance;
  return `${intro("FINANCIAL UNDERWRITING","Test the assumptions","Change acquisition, rent, operating expenses or financing. Every output stays a hypothetical scenario until inputs are verified.",`<button class="btn" data-view="scope">← Edit scope</button><button class="btn primary" data-view="scenarios">Compare timing →</button>`)}
    <div class="support-note"><span>i</span><div><strong>Scenario math only.</strong> The rent reference is simulated asking-rent evidence. Cash flow, DSCR, and cash-on-cash are not a property approval or investment recommendation.</div></div>
    <form class="panel" id="financialForm"><div class="panel-heading"><div><h2>${esc(p.label)} · editable assumptions</h2><p>Fields start from the fictional property fixture and can be changed for sensitivity testing.</p></div><span class="evidence-stamp">SCENARIO ONLY</span></div>
      <div class="form-panel"><h3>Acquisition &amp; revenue</h3><div class="form-grid">${FINANCE_FIELDS.slice(0,3).map(x=>financeField(x,fin.inputs)).join("")}</div></div>
      <div class="form-panel"><h3>Operating assumptions</h3><div class="form-grid">${FINANCE_FIELDS.slice(3,8).map(x=>financeField(x,fin.inputs)).join("")}</div></div>
      <div class="form-panel"><h3>Financing &amp; cash needs</h3><div class="form-grid">${FINANCE_FIELDS.slice(8).map(x=>financeField(x,fin.inputs)).join("")}</div></div>
      <div class="button-row" style="margin-top:14px"><button class="btn primary" type="submit">Recalculate financials</button><button class="btn" type="button" id="resetFinance">Restore sample assumptions</button></div></form>
    <section class="panel"><div class="panel-heading"><div><h2>Preliminary financial results</h2><p>Calculated from the current editable assumptions and scope draft</p></div><span class="evidence-stamp">SIMULATED INPUTS</span></div>${resultCards(fin)}</section>
    <section class="panel"><div class="panel-heading"><div><h2>Project uses · amount explained</h2><p>Trace the headline total back to the entered assumptions</p></div><strong class="scope-total">${money(fin.metrics.project_uses)}</strong></div>${projectUsesTable(fin)}<p class="scope-method">This is an illustrative acquisition-use total. Financing proceeds and cash invested are shown separately; timing carry is excluded here and displayed in Scenarios.</p></section>
    <section class="panel"><div class="panel-heading"><div><h2>What is included</h2><p>Plain-language definitions</p></div></div><div class="evidence-list"><div class="evidence-row"><strong>NOI</strong><span>Effective scheduled rent less entered operating expense assumptions</span></div><div class="evidence-row"><strong>DSCR</strong><span>NOI ÷ modeled annual principal-and-interest debt service</span></div><div class="evidence-row"><strong>Cash flow</strong><span>(NOI − annual debt service) ÷ 12</span></div><div class="evidence-row"><strong>Cash-on-cash</strong><span>Annual stabilized cash flow ÷ modeled cash invested</span></div><div class="evidence-row"><strong>Excluded</strong><span>Income taxes, sale/refinance proceeds, and unknown property-specific costs</span></div></div></section>`;
}

function renderScenarios(){
  const a=state.analysis,t=a.timing, max=Math.max(...t.map(c=>Math.abs(c.first_year_operating_cash_flow)),1);
  const rows=t.map(c=>`<tr><td><strong>${c.construction_weeks}-week construction</strong></td><td>${c.repair_months}</td><td>${c.lease_up_months}</td><td>${c.no_rent_months}</td><td>${money(c.first_year_operating_cash_flow)}</td><td>${money(c.additional_uses)}</td><td>${money(c.project_uses_including_timing)}</td><td>${percent(c.annualized_stabilized_cash_on_cash)}</td></tr>`).join("");
  const bars=t.map(c=>`<div class="scenario-bar-row"><span>${c.construction_weeks} weeks</span><div class="bar-track"><div class="bar-fill ${c.first_year_operating_cash_flow<0?"negative":""}" style="width:${Math.max(4,Math.abs(c.first_year_operating_cash_flow)/max*100)}%"></div></div><span class="scenario-figure">${money(c.first_year_operating_cash_flow)}</span></div>`).join("");
  return `${intro("SCENARIO COMPARISON","See how timing changes year one","Rent and financing stay the same while construction time changes. You can edit lease-up and carry costs below.",`<button class="btn" data-view="financials">← Financial assumptions</button><button class="btn primary" data-view="report">Open report →</button>`)}
    <section class="panel"><div class="panel-heading"><div><h2>Construction timing sensitivity</h2><p>Year-one cash flow and total uses under the same scenario</p></div><span class="evidence-stamp">DETERMINISTIC SCENARIO</span></div>
      <form id="timingForm" class="scope-toolbar"><div class="field"><label for="leaseMonths">Lease-up months</label><input id="leaseMonths" name="lease_up_months" type="number" min="0" max="24" step="1" value="${state.timingInputs.lease_up_months}"></div><div class="field"><label for="carryCost">Monthly carry cost during pre-stabilization</label><input id="carryCost" name="monthly_carry_cost" type="number" min="0" step="50" value="${state.timingInputs.monthly_carry_cost}"></div><button class="btn primary" type="submit">Update sensitivity</button></form>
      <div class="scenario-bars">${bars}</div><div class="table-wrap"><table class="data-table"><thead><tr><th>Timeline</th><th>Repair months</th><th>Lease-up</th><th>No-rent months</th><th>Year-one operating cash flow</th><th>Added carry uses</th><th>Total project uses</th><th>Annualized stabilized CoC</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="support-note"><span>i</span><div><strong>How to read this:</strong> Annualized cash-on-cash is not the return for year one. The first-year figure allows for lost rent during repairs and lease-up, plus the entered carry cost. Repair time is rounded up to a full month; this is a demo rule, not a construction forecast.</div></div>
    </section><section class="panel"><div class="panel-heading"><div><h2>Scenario controls</h2><p>Change these inputs on the Financials page.</p></div></div><div class="mini-stats"><div class="mini-stat"><span>Property + scope</span><strong>${money(a.finance.inputs.purchase_price + a.scope.total)}</strong></div><div class="mini-stat"><span>Monthly rent assumption</span><strong>${money(a.finance.inputs.monthly_rent)}</strong></div><div class="mini-stat"><span>Baseline monthly cash flow</span><strong>${money(a.finance.metrics.monthly_cash_flow)}</strong></div></div></section>`;
}

function renderReport(){
  const a=state.analysis,p=selectedProperty(),m=selectedMarket(),f=a.finance.metrics,inputs=a.finance.inputs,s=a.scope;
  const scopeRows=s.lines.map(line=>`<tr><td>${esc(line.label)}</td><td>${money(line.base)}</td><td>${line.supporting_projects} fictional analogs</td></tr>`).join("");
  const saleRows=a.sales.map(c=>`<tr><td>${esc(c.label)}</td><td>${money(c.sale_price)}</td><td>${number(c.sqft)}</td><td>${c.beds} bd / ${c.baths} ba</td></tr>`).join("");
  return `${intro("PRELIMINARY ACQUISITION REPORT","Review the sample analysis","The report brings the property, renovation scope, and financial scenario together for printing.",`<button class="btn" data-view="property">Back to workspace</button><button class="btn primary" id="printReport">Print / save as PDF</button>`)}
    <article class="report-preview" id="reportDocument"><header class="report-cover"><div class="eyebrow">PROPERTY INTELLIGENCE LAB · FICTIONAL PORTFOLIO CASE</div><h2>Preliminary property analysis</h2><p>${esc(p.label)} · ${esc(m.name)} · fictional example data</p></header><div class="report-body">
      <div class="report-section"><div class="report-callout"><strong>Fictional demo data.</strong> This report is not a real property analysis, appraisal, contractor quote, loan request, or investment recommendation.</div></div>
      <section class="report-section"><h3>Property snapshot</h3><div class="report-facts"><div class="report-fact"><span>Asking assumption</span><strong>${money(inputs.purchase_price)}</strong></div><div class="report-fact"><span>Rent assumption</span><strong>${money(inputs.monthly_rent)}/mo</strong></div><div class="report-fact"><span>Existing facts</span><strong>${p.beds} bd · ${p.baths} ba</strong></div><div class="report-fact"><span>Living area</span><strong>${number(p.sqft)} sqft</strong></div></div><div class="report-facts" style="margin-top:9px"><div class="report-fact"><span>Comparable sale median</span><strong>${money(a.value_reference.median_comparable_sale)}</strong></div><div class="report-fact"><span>Renovation scenario</span><strong>${money(s.total)}</strong></div><div class="report-fact"><span>Monthly cash flow</span><strong>${money(f.monthly_cash_flow)}</strong></div><div class="report-fact"><span>DSCR</span><strong>${f.dscr?.toFixed(2) ?? "Unavailable"}</strong></div></div></section>
      <section class="report-section"><h3>Property and market evidence</h3><p class="page-subtitle">${esc(p.description)} Market context: ${esc(m.profile)} All facts and three sales / three rental observations are synthetic examples.</p><h4>Comparable sales</h4><div class="table-wrap"><table class="data-table"><thead><tr><th>Fictional comp</th><th>Sale price</th><th>Area</th><th>Layout</th></tr></thead><tbody>${saleRows}</tbody></table></div><p class="scope-method">Rental reference median: ${money(a.rent_reference.median_comparable_asking_rent)} / month. The examples are simulated asking rents, not achieved or approved rents.</p></section>
      <section class="report-section"><h3>Preliminary renovation budget</h3><p class="scope-method">Strategy: ${esc(s.strategy.replaceAll("_"," "))}. ${esc(s.method)}</p><div class="table-wrap"><table class="data-table"><thead><tr><th>Work package</th><th>Scenario estimate</th><th>Synthetic analogs</th></tr></thead><tbody>${scopeRows}<tr><td><strong>Total preliminary scope</strong></td><td><strong>${money(s.total)}</strong></td><td>Contractor review pending</td></tr></tbody></table></div></section>
      <section class="report-section"><h3>Financial scenario</h3><div class="mini-stats"><div class="mini-stat"><span>Estimated NOI</span><strong>${money(f.estimated_noi)}</strong></div><div class="mini-stat"><span>Annual debt service</span><strong>${money(f.annual_debt_service)}</strong></div><div class="mini-stat"><span>Project uses</span><strong>${money(f.project_uses)}</strong></div></div>${projectUsesTable(a.finance)}<p class="scope-method">Scenario inputs: LTV ${percent(inputs.ltv)}, interest ${percent(inputs.interest_rate)}, term ${inputs.loan_term_years} years, vacancy ${percent(inputs.vacancy_rate)}. These assumptions are editable in the application. Timing carry is shown separately in the construction sensitivity section.</p></section>
      <section class="report-section"><h3>Construction timing sensitivity</h3><div class="table-wrap"><table class="data-table"><thead><tr><th>Duration</th><th>Repair + lease-up no-rent months</th><th>First-year operating CF</th><th>Added carry</th></tr></thead><tbody>${a.timing.map(t=>`<tr><td>${t.construction_weeks} weeks</td><td>${t.no_rent_months}</td><td>${money(t.first_year_operating_cash_flow)}</td><td>${money(t.additional_uses)}</td></tr>`).join("")}</tbody></table></div></section>
      <section class="report-section"><h3>Open review items</h3><ul>${a.audit.review_required.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></section><footer class="report-footer">Prepared by the public portfolio simulation · Model ${esc(a.audit.model_version)} · Corpus ${esc(a.audit.corpus_version)} · Not for lending, valuation, or acquisition decisions.</footer>
    </div></article>`;
}

const VIEWS={overview:renderOverview,markets:renderMarkets,properties:renderProperties,property:renderProperty,scope:renderScope,financials:renderFinancials,scenarios:renderScenarios,report:renderReport};
function render(){
  if(!demo||!state.analysis)return;
  $("#currentSection").textContent=title(state.view);
  document.title=`${title(state.view)} · Property Intelligence Lab`;
  document.querySelectorAll(".nav-item").forEach(item=>item.classList.toggle("active",item.dataset.view===state.view));
  $("#main").innerHTML=VIEWS[state.view]();
}

function navigate(view){
  if(!VIEWS[view])return;
  state.view=view;document.body.classList.remove("nav-open");$("#menuToggle").setAttribute("aria-expanded","false");render();$("#main").focus({preventScroll:true});window.scrollTo({top:0,behavior:"smooth"});
}

async function openProperty(propertyId){
  state.selectedId=propertyId;state.scopeOverrides={};state.strategy="interior_refresh";state.financialInputs={};await runAnalysis(false);navigate("property");
}

function refreshPropertyCards(){
  const target=$("#propertyResults");if(target)target.innerHTML=visibleProperties().map(propertyCard).join("")||`<div class="empty-state"><strong>No sample properties match</strong>Clear the search or choose another demo market.</div>`;
}

document.addEventListener("click",async event=>{
  const viewButton=event.target.closest("[data-view]");
  if(viewButton){event.preventDefault();navigate(viewButton.dataset.view);return;}
  const openButton=event.target.closest("[data-open-property]");
  if(openButton){await openProperty(openButton.dataset.openProperty);return;}
  const filterButton=event.target.closest("[data-filter-market]");
  if(filterButton){state.marketFilter=filterButton.dataset.filterMarket;state.search="";navigate("properties");return;}
  if(event.target.id==="dismissNotice"){$(".notice-bar").classList.add("is-hidden");return;}
  if(event.target.id==="menuToggle"){const open=!document.body.classList.contains("nav-open");document.body.classList.toggle("nav-open",open);event.target.setAttribute("aria-expanded",String(open));event.target.setAttribute("aria-label",open?"Close navigation":"Open navigation");return;}
  if(event.target.id==="mobileScrim"){document.body.classList.remove("nav-open");$("#menuToggle").setAttribute("aria-expanded","false");return;}
  if(event.target.id==="recalculateScope"){
    state.strategy=$("#strategySelect").value;await runAnalysis();render();return;
  }
  if(event.target.id==="applyScopeEdits"){
    document.querySelectorAll("[data-scope-cost]").forEach(input=>state.scopeOverrides[input.dataset.scopeCost]=Number(input.value));await runAnalysis();render();return;
  }
  if(event.target.id==="resetScopeEdits"){
    state.scopeOverrides={};await runAnalysis();render();return;
  }
  if(event.target.id==="resetFinance"){
    state.financialInputs={};await runAnalysis();render();return;
  }
  if(event.target.id==="printReport"){window.print();return;}
});

document.addEventListener("input",event=>{
  if(event.target.id==="propertySearch"){state.search=event.target.value;refreshPropertyCards();}
});
document.addEventListener("change",event=>{
  if(event.target.id==="marketFilter"){state.marketFilter=event.target.value;refreshPropertyCards();}
  if(event.target.id==="strategySelect"){state.strategy=event.target.value;}
});
document.addEventListener("submit",async event=>{
  if(event.target.id==="financialForm"){
    event.preventDefault();const form=new FormData(event.target);state.financialInputs={};for(const [key,value] of form.entries())state.financialInputs[key]=Number(value);await runAnalysis();render();return;
  }
  if(event.target.id==="timingForm"){
    event.preventDefault();const form=new FormData(event.target);state.timingInputs={lease_up_months:Number(form.get("lease_up_months")),monthly_carry_cost:Number(form.get("monthly_carry_cost"))};await runAnalysis();render();return;
  }
});

init();
