//! Behavioral annotations and per-command metadata.
//!
//! Annotation hint keys (`readOnlyHint`, `idempotentHint`, etc.) are camelCase
//! to match the MCP tool definition convention. Other Tooli keys
//! (`description`, `capabilities`, `examples`) stay snake_case alongside the
//! envelope.

use crate::util::is_false;
use serde::Serialize;

/// Behavioral annotations used by agents and policy layers.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Annotation {
    ReadOnly,
    Idempotent,
    Destructive,
    OpenWorld,
}

/// Serialized annotation hints (camelCase, MCP-compatible).
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize)]
pub struct AnnotationSet {
    #[serde(rename = "readOnlyHint", skip_serializing_if = "is_false")]
    pub read_only: bool,
    #[serde(rename = "idempotentHint", skip_serializing_if = "is_false")]
    pub idempotent: bool,
    #[serde(rename = "destructiveHint", skip_serializing_if = "is_false")]
    pub destructive: bool,
    #[serde(rename = "openWorldHint", skip_serializing_if = "is_false")]
    pub open_world: bool,
}

impl AnnotationSet {
    pub fn add(&mut self, annotation: Annotation) {
        match annotation {
            Annotation::ReadOnly => self.read_only = true,
            Annotation::Idempotent => self.idempotent = true,
            Annotation::Destructive => self.destructive = true,
            Annotation::OpenWorld => self.open_world = true,
        }
    }

    pub fn with(mut self, annotation: Annotation) -> Self {
        self.add(annotation);
        self
    }

    pub fn is_empty(&self) -> bool {
        !self.read_only && !self.idempotent && !self.destructive && !self.open_world
    }
}

/// Example invocation included in command schema output.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Example {
    pub command: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

impl Example {
    pub fn new(command: impl Into<String>) -> Self {
        Self {
            command: command.into(),
            description: None,
        }
    }

    pub fn description(mut self, description: impl Into<String>) -> Self {
        self.description = Some(description.into());
        self
    }
}

/// Agent-facing command metadata.
#[derive(Debug, Clone, Default, Serialize)]
pub struct CommandMeta {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(default, skip_serializing_if = "AnnotationSet::is_empty")]
    pub annotations: AnnotationSet,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub capabilities: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub examples: Vec<Example>,
    #[serde(default, skip_serializing_if = "is_false")]
    pub deprecated: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deprecated_message: Option<String>,
    #[serde(
        rename = "requiresConfirmation",
        default,
        skip_serializing_if = "is_false"
    )]
    pub requires_confirmation: bool,
}

impl CommandMeta {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn description(mut self, description: impl Into<String>) -> Self {
        self.description = Some(description.into());
        self
    }

    pub fn annotation(mut self, annotation: Annotation) -> Self {
        self.annotations.add(annotation);
        self
    }

    pub fn capability(mut self, capability: impl Into<String>) -> Self {
        self.capabilities.push(capability.into());
        self
    }

    pub fn example(mut self, command: impl Into<String>) -> Self {
        self.examples.push(Example::new(command));
        self
    }

    pub fn example_with_description(
        mut self,
        command: impl Into<String>,
        description: impl Into<String>,
    ) -> Self {
        self.examples
            .push(Example::new(command).description(description));
        self
    }

    pub fn deprecated(mut self, message: impl Into<String>) -> Self {
        self.deprecated = true;
        self.deprecated_message = Some(message.into());
        self
    }

    pub fn requires_confirmation(mut self) -> Self {
        self.requires_confirmation = true;
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn annotation_set_tracks_added_hints() {
        let set = AnnotationSet::default()
            .with(Annotation::ReadOnly)
            .with(Annotation::Idempotent);

        assert!(set.read_only);
        assert!(set.idempotent);
        assert!(!set.destructive);
        assert!(!set.is_empty());
    }
}
