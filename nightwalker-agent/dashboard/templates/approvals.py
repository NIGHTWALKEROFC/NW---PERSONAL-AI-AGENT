{% extends "base.html" %}
{% block title %}Approvals — NightWalker{% endblock %}
{% block content %}
<h2>Approval Center</h2>

{% if pending %}
{% for item in pending %}
<div class="card">
    <h3>{{ item.action_type.replace('_', ' ') }}</h3>
    <p class="muted">{{ item.reasoning }}</p>
    {% for key, value in item.payload.items() %}
    <p><strong>{{ key.replace('_', ' ') }}:</strong> {{ value }}</p>
    {% endfor %}

    <form method="post" action="/approvals/approve" class="inline">
        <input type="hidden" name="approval_id" value="{{ item.id }}">
        <button type="submit">Approve</button>
    </form>

    <form method="post" action="/approvals/reject" class="inline">
        <input type="hidden" name="approval_id" value="{{ item.id }}">
        <button type="submit" class="danger">Reject</button>
    </form>

    <form method="post" action="/approvals/always-allow" class="inline">
        <input type="hidden" name="approval_id" value="{{ item.id }}">
        <input type="hidden" name="action_type" value="{{ item.action_type }}">
        <button type="submit">Always allow this action type</button>
    </form>

    <form method="post" action="/approvals/never-allow" class="inline">
        <input type="hidden" name="approval_id" value="{{ item.id }}">
        <input type="hidden" name="action_type" value="{{ item.action_type }}">
        <button type="submit" class="danger">Never allow this action type</button>
    </form>

    <form method="post" action="/approvals/edit" style="margin-top:12px;">
        <input type="hidden" name="approval_id" value="{{ item.id }}">
        <input type="text" name="new_text" placeholder="Edit and approve with different text...">
        <button type="submit">Approve with edits</button>
    </form>
</div>
{% endfor %}
{% else %}
<div class="card">
    <p class="not-built">No pending approvals right now.</p>
</div>
{% endif %}
{% endblock %}
