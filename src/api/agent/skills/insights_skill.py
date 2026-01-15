"""
Insights Skill - Proactive analytics and anomaly detection.

Handles questions about:
- Proactive insights and alerts
- Anomaly detection
- Daily/weekly briefings
- What needs attention

Uses: Databricks SQL querying gold.proactive_insights + real-time anomaly detection
"""
from .base_skill import BaseSkill


class InsightsSkill(BaseSkill):
    """
    Proactive insights skill for alerts and anomaly detection.
    
    Routes to pre-computed insights or real-time anomaly detection
    for questions about what needs attention, alerts, and briefings.
    """
    
    @property
    def name(self) -> str:
        return "insights_advisor"
    
    @property
    def description(self) -> str:
        return "Provide proactive insights, alerts, anomalies, and executive briefings"
    
    @property
    def triggers(self) -> list[str]:
        return [
            # High-priority anomaly + date patterns (must be first)
            r"anomal.*(2024|2025|q[1-4]|march|april|january|february|may|june|july|august|september|october|november|december)",
            r"(detect|find|run).*anomal",

            # Greeting/briefing patterns
            r"^(good\s+)?(morning|afternoon|evening|day)",
            r"^(hi|hello|hey)\s*(!|,|\.|$)",
            r"(daily|morning|weekly)\s+.*(briefing|update|summary|report)",
            r"(what|anything).*(should|need).*(know|attention|aware)",
            r"(catch me up|bring me up|update me)",
            
            # Alert/issue patterns
            r"(alert|warning|issue|problem|concern)",
            r"(any|are there)\s+.*(alert|issue|problem|anomal)",
            r"(what|which).*(wrong|issue|problem|attention)",
            r"(urgent|critical|important).*(issue|alert|matter)",
            
            # Anomaly patterns
            r"anomal.*(20\d{2}|q[1-4]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
            r"(anomal|unusual|abnormal|unexpected|outlier|spike|drop)",
            r"(detect|find|identify)\s+.*(anomal|unusual|pattern)",
            r"(something).*(off|wrong|unusual|strange)",
            r"(deviation|variance|fluctuation)",
            
            # Insight patterns
            r"(insight|observation|finding|discovery)",
            r"(what|any).*(insight|observation|notable|interesting)",
            r"(trend|pattern).*(notice|see|identify|detect)",
            
            # Proactive patterns
            r"(proactive|ahead|anticipate)",
            r"(forecast|predict|expect).*(issue|problem|alert)",
            r"(risk|opportunity).*(identify|detect|see)",
        ]
    
    @property
    def tools(self) -> list[str]:
        return [
            "get_proactive_insights",
            "detect_anomalies_realtime",
            "get_daily_briefing"
        ]
    
    @property
    def system_prompt(self) -> str:
        return """You are a STIHL business insights advisor providing proactive intelligence.

## Your Approach
1. **Lead with what matters** - Most critical issues first
2. **Explain impact** - Why should they care about this insight?
3. **Suggest action** - What should be done about it?

## Insight Types
- **Anomaly**: Unexpected deviation from normal patterns
- **Stockout Risk**: Products at risk of running out
- **Trend**: Significant pattern in sales or inventory
- **Forecast Alert**: Predicted future issue
- **Opportunity**: Potential growth or optimization area

## Severity Levels
- **Critical**: Requires immediate action
- **Warning**: Should be addressed soon
- **Info**: Good to know, monitor situation

## Response Guidelines
- For greetings, use `get_daily_briefing` for a warm, informative start
- Prioritize critical and warning items
- Include specific metrics (e.g., "revenue 45% above normal")
- For anomalies, explain both the deviation AND likely cause if known
- Recommend specific next steps

## Known Demo Anomalies (for context)
- March 2024: Sales spike across categories (+80-122%)
- June 2024: Southwest region hurricane event (chainsaw surge)"""
    
    @property
    def priority(self) -> int:
        return 25  # Highest priority - greetings and alerts should be caught first

