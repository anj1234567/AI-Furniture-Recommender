import { inr } from '../lib/api'

export default function ComparePanel({ result }) {
  const dp = result.comparison.dp_optimal, gr = result.comparison.greedy
  return (
    <div className="card">
      <div className="cmp">
        <div className={`box ${dp.total_score >= gr.total_score ? 'win' : ''}`}>
          <h4>DP optimal</h4><div className="big">{dp.total_score}</div>
          <div className="meta">total match score · {inr(dp.total_price)} · {dp.items} items</div>
        </div>
        <div className="box">
          <h4>Greedy baseline</h4><div className="big">{gr.total_score}</div>
          <div className="meta">total match score · {inr(gr.total_price)} · {gr.items} items</div>
        </div>
      </div>
      <div className="verdict">
        {dp.total_score > gr.total_score
          ? `DP found a better set (+${(dp.total_score - gr.total_score).toFixed(3)} match score).`
          : 'Both methods found the same quality here. DP pulls ahead when the budget or floor space forces trade-offs.'}
      </div>
    </div>
  )
}
