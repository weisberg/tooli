//! Stable JSON envelopes for success and error results.
//!
//! Envelope keys are snake_case to match the Python Tooli contract. The two
//! envelopes are intentionally asymmetric: success has no `error` key, error
//! has a `result: null` key so consumers can branch on `ok` first and still
//! locate `result` without a missing-key check.

use crate::util::is_false;
use crate::ToolError;
use serde::Serialize;
use serde_json::Value;

/// Metadata attached to every machine-readable Tooli envelope.
#[derive(Debug, Clone, Serialize)]
pub struct EnvelopeMeta {
    pub tool: String,
    pub version: String,
    pub duration_ms: u128,
    #[serde(default, skip_serializing_if = "is_false")]
    pub dry_run: bool,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub warnings: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub caller_id: Option<String>,
}

impl EnvelopeMeta {
    pub fn new(tool: impl Into<String>, version: impl Into<String>, duration_ms: u128) -> Self {
        Self {
            tool: tool.into(),
            version: version.into(),
            duration_ms,
            dry_run: false,
            warnings: Vec::new(),
            caller_id: None,
        }
    }

    pub fn dry_run(mut self, dry_run: bool) -> Self {
        self.dry_run = dry_run;
        self
    }

    pub fn caller_id(mut self, caller_id: Option<String>) -> Self {
        self.caller_id = caller_id;
        self
    }

    pub fn warning(mut self, warning: impl Into<String>) -> Self {
        self.warnings.push(warning.into());
        self
    }
}

/// Successful machine-readable envelope.
#[derive(Debug, Serialize)]
pub struct SuccessEnvelope<'a, T: Serialize> {
    pub ok: bool,
    pub result: &'a T,
    pub meta: EnvelopeMeta,
}

impl<'a, T: Serialize> SuccessEnvelope<'a, T> {
    pub fn new(result: &'a T, meta: EnvelopeMeta) -> Self {
        Self {
            ok: true,
            result,
            meta,
        }
    }
}

/// Failed machine-readable envelope. `result` is always `null`; consumers can
/// branch on `ok` and still address `result` uniformly.
#[derive(Debug, Serialize)]
pub struct ErrorEnvelope {
    pub ok: bool,
    pub error: ToolError,
    pub meta: EnvelopeMeta,
    pub result: Option<Value>,
}

impl ErrorEnvelope {
    pub fn new(error: ToolError, meta: EnvelopeMeta) -> Self {
        Self {
            ok: false,
            error,
            meta,
            result: None,
        }
    }
}
