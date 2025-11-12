#!/bin/bash
# Apply remaining patches

# 1. Update stats to include dropped_offtopic
sed -i 's/"retrieved": raw_trove_count + raw_web_count,/"retrieved": raw_trove_count + raw_web_count,\n            "dropped_offtopic": dropped,/' app/services/deep_research.py

# 2. Update effective_max usage
sed -i 's/: req\.max_sources/: effective_max/g' app/services/deep_research.py

# 3. Add UI drift badge
grep -q "dropped_offtopic" app/static/js/research.js || sed -i '/currentReport = report;/a\
    \
    // Show off-topic drop badge if backend set stats\
    if (report?.stats?.dropped_offtopic > 0) {\
      const progressStatus = document.getElementById("progressStatus");\
      if (progressStatus) {\
        progressStatus.innerHTML = `✅ Complete (filtered ${report.stats.dropped_offtopic} off-topic hits)`;\
        progressStatus.style.color = "#b45309";\
      }\
    }' app/static/js/research.js

echo "✅ Patches applied"
