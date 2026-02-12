# Luxer One

This custom Home Assistant component exposes a sensor per location which represents any pending Luxer One packages awaiting pickup. It updates every five minutes.

The sensor state represents the number of packages at the location, and there is an attribute `packages_json` which contains the raw JSON response from the Luxer One API. This is useful if you want to incorporate any of these details in your automations or other templates. For example, you can get the picture from the most recently delivered package with this template (substituting the sensor name for your own):

```jinja
{% set packages = state_attr("sensor.pending_luxer_packages", "packages_json") %}
{% if packages | length > 0 %}
   {{ packages[0]["labels"][0] }}
{% endif %}
```