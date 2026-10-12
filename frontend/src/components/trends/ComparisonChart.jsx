import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ReferenceLine,
  LabelList
} from 'recharts'
import { Sparkles } from 'lucide-react'

// Custom label to draw a pointer/sparkle above bars that have AI insights
const CustomLabel = (props) => {
  const { x, y, width, height, value, insights, index, data } = props
  // Recharts label doesn't pass payload directly in all cases, but we can look it up from data using index
  const payload = data && data[index]
  if (!payload) return null;
  
  const hasInsight = insights?.some(i => i.parameter === payload.parameter)
  if (!hasInsight) return null;

  // y is the coordinate of the bar's tip. If value is negative, y is at the bottom.
  const yPos = value >= 0 ? y - 15 : y + height + 15
  
  return (
    <svg x={x + width / 2 - 8} y={yPos - 8} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E11D48" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
    </svg>
  )
}

const CustomTooltip = ({ active, payload, label, insights = [] }) => {
  if (active && payload && payload.length) {
    const data = payload[0]?.payload
    if (!data) return null;
    const insightObj = insights?.find(i => i?.parameter === data.parameter)
    
    return (
      <div className="bg-white/95 backdrop-blur shadow-lg border border-ink/10 rounded-xl p-4 max-w-xs">
        <p className="font-semibold text-ink text-sm">{data.parameter}</p>
        <div className="mt-2 grid grid-cols-2 gap-4 text-xs">
          <div>
            <p className="text-ink-soft mb-0.5">Old Value</p>
            <p className="font-medium text-ink">{data.old_value}</p>
          </div>
          <div>
            <p className="text-ink-soft mb-0.5">New Value</p>
            <p className="font-medium text-ink">{data.new_value}</p>
          </div>
        </div>
        <div className="mt-3 border-t border-ink/5 pt-3">
          <p className="text-sm font-medium text-ink flex items-center gap-1 mb-1">
             % Change: <span className={(data.percent_change || 0) > 0 ? 'text-rose-600' : 'text-emerald-600'}>
               {(data.percent_change || 0) > 0 ? '+' : ''}{data.percent_change}%
             </span>
          </p>
          {insightObj?.insight && (
            <div className="mt-2 bg-rose-50 text-rose-900 rounded-lg p-2 text-xs leading-relaxed flex gap-2">
              <Sparkles size={14} className="shrink-0 mt-0.5 text-rose-500" />
              <span>{insightObj.insight}</span>
            </div>
          )}
        </div>
      </div>
    )
  }
  return null
}

export default function ComparisonChart({ chartData, data, insights = [] }) {
  const items = chartData || data || []
  if (!items || items.length === 0) {
    return (
      <div className="h-64 w-full flex items-center justify-center text-ink-soft text-sm">
        No common parameters found to compare.
      </div>
    )
  }

  return (
    <div className="h-96 w-full mt-6 pb-8">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={items} margin={{ top: 20, right: 12, bottom: 100, left: -12 }}>
          <CartesianGrid stroke="#1B2A4114" vertical={false} />
          <XAxis 
            dataKey="parameter" 
            tick={{ fontSize: 11, fill: '#4A5D73' }} 
            axisLine={false} 
            tickLine={false} 
            interval={0}
            angle={-45}
            textAnchor="end"
          />
          <YAxis 
            tick={{ fontSize: 12, fill: '#4A5D73' }} 
            axisLine={false} 
            tickLine={false} 
            width={50} 
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip 
            content={<CustomTooltip insights={insights} />}
            cursor={{ fill: '#1B2A4108' }}
          />
          <ReferenceLine y={0} stroke="#1B2A41" strokeOpacity={0.2} />
          <Bar 
            dataKey="percent_change" 
            radius={[4, 4, 4, 4]}
          >
            <LabelList content={<CustomLabel insights={insights} data={items} />} />
            {items.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={(entry?.percent_change || 0) > 0 ? '#E11D48' : '#059669'} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
