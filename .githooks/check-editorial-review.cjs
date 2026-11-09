const { execFileSync } = require('node:child_process');
const { readFileSync } = require('node:fs');
const { isDeepStrictEqual } = require('node:util');

function analysesAt(ref) {
  return JSON.parse(execFileSync('git', ['show', ref + ':data/analyses.json'], { encoding: 'utf8' }));
}

function validReference(reference) {
  if (typeof reference?.locator !== 'string' || !reference.locator.trim()) return false;
  try {
    return ['https:', 'http:'].includes(new URL(reference.url).protocol);
  } catch {
    return false;
  }
}

for (const update of readFileSync(0, 'utf8').trim().split(/\r?\n/)) {
  const [, localSha, remoteRef, remoteSha] = update.split(/\s+/);
  if (remoteRef !== 'refs/heads/main' || /^0+$/.test(localSha)) continue;

  const previous = analysesAt(remoteSha);
  const next = analysesAt(localSha);
  for (const [url, analysis] of Object.entries(next)) {
    if (isDeepStrictEqual(previous[url], analysis)) continue;

    const review = analysis.editorial_review;
    if (
      !Array.isArray(analysis.points) || !analysis.points.length ||
      !Array.isArray(review) || review.length !== analysis.points.length ||
      !review.every(validReference) ||
      (previous[url] && isDeepStrictEqual(previous[url].editorial_review, review))
    ) {
      console.error('Relecture à consigner pour chaque point avant publication : ' + url);
      process.exitCode = 1;
    }
  }
}
