// JEPXスポット価格ダッシュボードのウィジェット（Übersicht用）
// ウィジェットの中の画面にはクリックが届かないことがあるため、切り替えボタンはウィジェット側（上部）に置いている
import { run } from "uebersicht";

const BASE = "https://munetomoando.github.io/jepx-dashboard/";
const ZOOM = 0.8;            // 表示の縮小率（ページ自身が縮小する）
const W = 1100, H = 780;     // ダッシュボード本来の大きさ
const VIEWS = [
  ["今日", {}],
  ["明日", { date: "tomorrow" }],
  ["長期の推移", { page: "long" }],
  ["気象と価格", { page: "analysis" }],
];

export const refreshFrequency = false;  // 画面側が5分ごとに自分でデータを読み直し、日付の変わり目も追いかける
export const initialState = { view: 0, reload: 0 };
export const updateState = (e, prev) =>
  e.type === "VIEW" ? { view: e.view, reload: prev.reload + 1 } : prev;

const query = (view, extra = {}) => new URLSearchParams({ ...VIEWS[view][1], ...extra }).toString();

export const className = `
  top: 40px; left: 40px;               /* 画面上の位置 */
  border-radius: 12px; overflow: hidden;
  box-shadow: 0 8px 30px rgba(0,0,0,.35);
  font-family: -apple-system, "Hiragino Sans", sans-serif;
  --bar: #222D3E; --on: #33415A; --text: #E8ECF2; --muted: #8E9AAD; --bg: #1C2533;
  @media (prefers-color-scheme: light) {
    --bar: #FFFFFF; --on: #D2D9E3; --text: #1B2533; --muted: #5B6778; --bg: #EDF0F4;
  }
  background: var(--bg);
  .bar { display: flex; gap: 6px; padding: 8px 10px; background: var(--bar); border-bottom: 1px solid var(--on); }
  button { font: inherit; font-size: 12px; padding: 5px 12px; border: 0; border-radius: 6px;
           cursor: pointer; color: var(--muted); background: transparent; }
  button.on { color: var(--text); background: var(--on); }
  button.open { margin-left: auto; }
  iframe { display: block; border: 0; }
`;

export const render = ({ view, reload }, dispatch) => (
  <div>
    <div className="bar">
      {VIEWS.map(([label], i) => (
        <button key={label} className={i === view ? "on" : ""} onClick={() => dispatch({ type: "VIEW", view: i })}>
          {label}
        </button>
      ))}
      <button className="open" onClick={() => run(`open "${BASE}?${query(view)}"`)}>ブラウザで開く ↗</button>
    </div>
    <iframe key={reload} src={`${BASE}?${query(view, { zoom: ZOOM, embed: 1, r: reload })}`}
      style={{ width: W * ZOOM, height: H * ZOOM }} />
  </div>
);
