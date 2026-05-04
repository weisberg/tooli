//! Structured Tooli errors with stable JSON shape.
//!
//! `ToolError` keeps its bulkiest optional fields (`Suggestion`) behind a
//! `Box` so that `Result<T, ToolError>` stays well below the
//! `clippy::result_large_err` threshold without an `#[allow]`.

use crate::util::is_false;
use serde::Serialize;
use serde_json::Value;
use std::collections::BTreeMap;
use thiserror::Error;

/// Stable high-level error category. Serialized as snake_case to match the
/// Python Tooli envelope contract.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCategory {
    Input,
    Auth,
    State,
    Runtime,
    Internal,
}

impl ErrorCategory {
    pub fn default_code(self) -> &'static str {
        match self {
            ErrorCategory::Input => "E1000",
            ErrorCategory::Auth => "E2000",
            ErrorCategory::State => "E3000",
            ErrorCategory::Runtime => "E4000",
            ErrorCategory::Internal => "E5000",
        }
    }

    pub fn exit_code(self) -> u8 {
        match self {
            ErrorCategory::Input => 2,
            ErrorCategory::State => 10,
            ErrorCategory::Auth => 30,
            ErrorCategory::Runtime | ErrorCategory::Internal => 70,
        }
    }
}

/// Agent-readable recovery guidance.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Suggestion {
    pub action: String,
    pub fix: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub example: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub applicability: Option<String>,
}

impl Suggestion {
    pub fn new(action: impl Into<String>, fix: impl Into<String>) -> Self {
        Self {
            action: action.into(),
            fix: fix.into(),
            example: None,
            applicability: None,
        }
    }

    pub fn retry(fix: impl Into<String>, example: impl Into<String>) -> Self {
        Self {
            action: "retry_with_modified_input".to_string(),
            fix: fix.into(),
            example: Some(example.into()),
            applicability: None,
        }
    }

    pub fn example(mut self, example: impl Into<String>) -> Self {
        self.example = Some(example.into());
        self
    }

    pub fn applicability(mut self, applicability: impl Into<String>) -> Self {
        self.applicability = Some(applicability.into());
        self
    }
}

/// Structured Tooli error.
///
/// Field naming matches the Python envelope (snake_case keys: `is_retryable`,
/// `details`). The bulky `Suggestion` is heap-allocated so that the common
/// no-suggestion path keeps `Result<T, ToolError>` cheap.
#[derive(Debug, Clone, Error, Serialize)]
#[error("{message}")]
pub struct ToolError {
    pub code: String,
    pub category: ErrorCategory,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suggestion: Option<Box<Suggestion>>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub is_retryable: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub field: Option<String>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub details: BTreeMap<String, Value>,
}

impl ToolError {
    pub fn new(category: ErrorCategory, message: impl Into<String>) -> Self {
        Self {
            code: category.default_code().to_string(),
            category,
            message: message.into(),
            suggestion: None,
            is_retryable: false,
            field: None,
            details: BTreeMap::new(),
        }
    }

    pub fn input(message: impl Into<String>) -> Self {
        Self::new(ErrorCategory::Input, message)
    }

    pub fn auth(message: impl Into<String>) -> Self {
        Self::new(ErrorCategory::Auth, message)
    }

    pub fn state(message: impl Into<String>) -> Self {
        Self::new(ErrorCategory::State, message)
    }

    pub fn runtime(message: impl Into<String>) -> Self {
        Self::new(ErrorCategory::Runtime, message)
    }

    pub fn internal(message: impl Into<String>) -> Self {
        Self::new(ErrorCategory::Internal, message)
    }

    pub fn code(mut self, code: impl Into<String>) -> Self {
        self.code = code.into();
        self
    }

    pub fn field(mut self, field: impl Into<String>) -> Self {
        self.field = Some(field.into());
        self
    }

    pub fn retryable(mut self, retryable: bool) -> Self {
        self.is_retryable = retryable;
        self
    }

    pub fn suggestion(mut self, suggestion: Suggestion) -> Self {
        self.suggestion = Some(Box::new(suggestion));
        self
    }

    pub fn detail(mut self, key: impl Into<String>, value: impl Into<Value>) -> Self {
        self.details.insert(key.into(), value.into());
        self
    }

    pub fn exit_code(&self) -> u8 {
        self.category.exit_code()
    }

    /// Borrow the optional suggestion without forcing callers to dereference
    /// the box.
    pub fn suggestion_ref(&self) -> Option<&Suggestion> {
        self.suggestion.as_deref()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn input_error_has_stable_exit_code() {
        let err = ToolError::input("bad input").field("pattern");

        assert_eq!(err.category, ErrorCategory::Input);
        assert_eq!(err.exit_code(), 2);
        assert_eq!(err.field.as_deref(), Some("pattern"));
    }

    #[test]
    fn tool_error_size_is_below_clippy_threshold() {
        // Sanity check: keep `Result<_, ToolError>` cheap. 128 is the default
        // `clippy::result_large_err` threshold.
        assert!(std::mem::size_of::<ToolError>() <= 128);
    }
}
