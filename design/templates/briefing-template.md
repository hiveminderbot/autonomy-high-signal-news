# Morning Briefing - {{DATE}}

*High-signal news for AI practitioners, software developers, and tech investors*

---

## 🤖 Artificial Intelligence

{% for item in ai_items %}
{{item.indicator}} **{{item.headline}}** - {{item.subhead}}
   Source: {{item.source}} | [Read more]({{item.url}})
   > {{item.summary}}
{% endfor %}

---

## 💻 Software Development

{% for item in dev_items %}
{{item.indicator}} **{{item.headline}}** - {{item.subhead}}
   Source: {{item.source}} | [Read more]({{item.url}})
   > {{item.summary}}
{% endfor %}

---

## 💰 Investment & Markets

{% for item in investment_items %}
{{item.indicator}} **{{item.headline}}** - {{item.subhead}}
   Source: {{item.source}} | [Read more]({{item.url}})
   > {{item.summary}}
{% endfor %}

---

## 🎯 Key Themes Today

| Theme | Stories | Signal |
|-------|---------|--------|
{% for theme in themes %}| **{{theme.name}}** | {{theme.story_count}} | {{theme.signal}} |
{% endfor %}

---

*Generated: {{TIMESTAMP}} | {{total_stories}} stories from {{source_count}} sources*

**Priority indicators:** 🔥 Breaking / Very High Signal | ⭐ Important | 📰 Regular
