/**
 * Check PR body for incomplete Test Plan checkboxes.
 * Rules:
 * - [일반] or [UI] checkboxes must be checked ([x]).
 * - [머지 후] checkboxes are allowed to be incomplete ([ ]).
 * - Checkboxes without prefix are treated as [일반] and must be checked.
 * - Auto-generated checkboxes (e.g. CI, lint) are not part of manually checked plans but if they exist, they must be checked unless post-merge.
 */

const fs = require('fs');

function checkBody(body) {
  const lines = body.split('\n');
  let inTestPlan = false;
  const incomplete = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // Section entry
    if (line.match(/^##?\s*Test\s*[pP]an/i) || line.match(/^##?\s*체크리스트/i)) {
      inTestPlan = true;
      continue;
    }

    // Heading exit (except sub-headings inside Test Plan if any)
    if (line.match(/^##?\s+/) && inTestPlan) {
      // If it's a completely new major section, we might have left the Test Plan.
      // But usually Test Plan goes until the end or next main heading.
      // We will check if the heading is not related to Test Plan
      if (!line.match(/test/i) && !line.match(/check/i) && !line.match(/검증/i)) {
        inTestPlan = false;
      }
    }

    // Match unchecked checkbox: - [ ] or * [ ]
    const checkboxMatch = line.match(/^[-*]\s*\[\s*\]\s*(.*)/);
    if (checkboxMatch) {
      const content = checkboxMatch[1].trim();

      // Check if it has "[머지 후]" prefix
      const isPostMerge = content.includes('[머지 후]') || content.includes('`[머지 후]`');

      if (!isPostMerge && inTestPlan) {
        incomplete.push({
          lineNum: i + 1,
          content: content
        });
      }
    }
  }

  return incomplete;
}

// Support running via GitHub Actions by reading file or environment variable
if (require.main === module) {
  let body = '';

  if (process.env.PR_BODY) {
    body = process.env.PR_BODY;
  } else if (process.argv[2]) {
    const filePath = process.argv[2];
    if (fs.existsSync(filePath)) {
      body = fs.readFileSync(filePath, 'utf8');
    } else {
      console.error(`File not found: ${filePath}`);
      process.exit(1);
    }
  } else {
    console.error('Usage: node check-test-plan.js <path_to_pr_body_file> or set PR_BODY env var');
    process.exit(1);
  }

  const incompleteItems = checkBody(body);

  if (incompleteItems.length > 0) {
    console.error('❌ Incomplete Test Plan checkboxes found (excluding [머지 후] items):');
    incompleteItems.forEach(item => {
      console.error(`  Line ${item.lineNum}: ${item.content}`);
    });
    process.exit(1);
  } else {
    console.log('✅ All required Test Plan checkboxes are completed!');
    process.exit(0);
  }
}

module.exports = { checkBody };
