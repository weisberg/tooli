//! Capability gating against `TOOLI_ALLOWED_CAPABILITIES`.

use crate::{CommandMeta, ToolError};
use serde_json::json;
use std::env;

/// Return true when all required capabilities are allowed by the current process.
///
/// Enforcement is opt-in: if `TOOLI_ALLOWED_CAPABILITIES` is unset or empty,
/// all capabilities are allowed. When set, it accepts comma- or
/// whitespace-separated entries. Exact matches, `*`, and namespace wildcards
/// such as `fs:*` are supported.
pub fn capabilities_allowed(required: &[String]) -> bool {
    missing_capabilities(required).is_empty()
}

/// Enforce command capabilities against `TOOLI_ALLOWED_CAPABILITIES`.
pub fn enforce_capabilities(meta: &CommandMeta) -> crate::Result<()> {
    let missing = missing_capabilities(&meta.capabilities);
    if missing.is_empty() {
        return Ok(());
    }

    Err(
        ToolError::auth("command requires capabilities that are not allowed")
            .code("E2001")
            .detail("required", json!(meta.capabilities))
            .detail("allowed", json!(allowed_capabilities()))
            .detail("missing", json!(missing))
            .suggestion(crate::Suggestion::new(
                "grant_capability",
                "Set TOOLI_ALLOWED_CAPABILITIES to include the required capability.",
            )),
    )
}

fn missing_capabilities(required: &[String]) -> Vec<String> {
    if required.is_empty() {
        return Vec::new();
    }

    let allowed = allowed_capabilities();
    if allowed.is_empty() {
        return Vec::new();
    }

    required
        .iter()
        .filter(|capability| !capability_matches_any(capability, &allowed))
        .cloned()
        .collect()
}

fn allowed_capabilities() -> Vec<String> {
    env::var("TOOLI_ALLOWED_CAPABILITIES")
        .ok()
        .map(|raw| {
            raw.split(|ch: char| ch == ',' || ch.is_whitespace())
                .map(str::trim)
                .filter(|item| !item.is_empty())
                .map(ToOwned::to_owned)
                .collect()
        })
        .unwrap_or_default()
}

fn capability_matches_any(required: &str, allowed: &[String]) -> bool {
    allowed
        .iter()
        .any(|candidate| capability_matches(required, candidate))
}

fn capability_matches(required: &str, allowed: &str) -> bool {
    if allowed == "*" || allowed == required {
        return true;
    }

    if let Some(namespace) = allowed.strip_suffix(":*") {
        return required
            .strip_prefix(namespace)
            .is_some_and(|tail| tail.starts_with(':'));
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capability_matching_supports_exact_and_namespace_wildcards() {
        assert!(capability_matches("fs:read", "fs:read"));
        assert!(capability_matches("fs:read", "fs:*"));
        assert!(capability_matches("net:write", "*"));
        assert!(!capability_matches("net:write", "fs:*"));
    }
}
