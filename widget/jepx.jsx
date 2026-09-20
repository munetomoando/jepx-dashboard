// JEPXスポット価格ダッシュボードのウィジェット
// 埋め込んだページの中はクリックが届かないため、切り替えボタンはÜbersicht側に置いている
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

export const refreshFrequency = false;  // 画面側が5分ごとに自分でデータを読み直す
export const initialState = { view: 0, reload: 0 };
export const updateState = (e, prev) =>
  e.type === "VIEW" ? { view: e.view, reload: prev.reload + 1 } : prev;

export const className = `
  top: 40px; left: 40px;               /* 画面上の位置 */
  border-radius: 12px; overflow: hidden;
  box-shadow: 0 8px 30px rgba(0,0,0,.35);
  background: #1C2533;
  font-family: -apple-system, "Hiragino Sans", sans-serif;
`;

const bar = { display: "flex", gap: 6, padding: "8px 10px", background: "#222D3E" };
const btn = (on) => ({
  font: "inherit", fontSize: 12, padding: "5px 12px", border: 0, borderRadius: 6, cursor: "pointer",
  color: on ? "#E8ECF2" : "#8E9AAD", background: on ? "#33415A" : "transparent",
});

export const render = ({ view, reload }, dispatch) => {
  const q = new URLSearchParams({ ...VIEWS[view][1], zoom: ZOOM, r: reload });
  return (
    <div>
      <div style={bar}>
        {VIEWS.map(([label], i) => (
          <button key={label} style={btn(i === view)} onClick={() => dispatch({ type: "VIEW", view: i })}>
            {label}
          </button>
        ))}
        <button style={{ ...btn(false), marginLeft: "auto" }} onClick={() => run(`open "${BASE}"`)}>
          ブラウザで開く ↗
        </button>
      </div>
      <iframe key={reload} src={`${BASE}?${q}`}
        style={{ width: W * ZOOM, height: H * ZOOM, border: 0, display: "block" }} />
    </div>
  );
};
