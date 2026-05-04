//! `InputSource` (file path or `-` stdin) and `SecretString` (redacting).

use schemars::{
    gen::SchemaGenerator,
    schema::{InstanceType, Metadata, Schema, SchemaObject, SingleOrVec},
    JsonSchema,
};
use serde::Serialize;
use std::fmt;
use std::fs;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::str::FromStr;

/// A CLI input source that can be a file path or stdin (`-`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InputSource {
    File(PathBuf),
    Stdin,
}

impl InputSource {
    pub fn read_to_string(&self) -> io::Result<String> {
        match self {
            Self::File(path) => fs::read_to_string(path),
            Self::Stdin => {
                let mut value = String::new();
                io::stdin().read_to_string(&mut value)?;
                Ok(value)
            }
        }
    }

    pub fn as_path(&self) -> Option<&Path> {
        match self {
            Self::File(path) => Some(path),
            Self::Stdin => None,
        }
    }
}

impl FromStr for InputSource {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        if value == "-" {
            Ok(Self::Stdin)
        } else if value.trim().is_empty() {
            Err("input source must not be empty".to_string())
        } else {
            Ok(Self::File(PathBuf::from(value)))
        }
    }
}

impl Serialize for InputSource {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        match self {
            Self::File(path) => serializer.serialize_str(&path.display().to_string()),
            Self::Stdin => serializer.serialize_str("-"),
        }
    }
}

impl JsonSchema for InputSource {
    fn schema_name() -> String {
        "InputSource".to_string()
    }

    fn json_schema(_gen: &mut SchemaGenerator) -> Schema {
        let mut object = SchemaObject {
            instance_type: Some(SingleOrVec::Single(Box::new(InstanceType::String))),
            ..SchemaObject::default()
        };
        object.metadata = Some(Box::new(Metadata {
            description: Some("File path or '-' for stdin.".to_string()),
            ..Metadata::default()
        }));
        Schema::Object(object)
    }
}

/// Secret string input that redacts itself in debug and serialized output.
#[derive(Clone, PartialEq, Eq)]
pub struct SecretString(String);

impl SecretString {
    pub fn new(value: impl Into<String>) -> Self {
        Self(value.into())
    }

    pub fn expose_secret(&self) -> &str {
        &self.0
    }

    pub fn into_inner(self) -> String {
        self.0
    }
}

impl fmt::Debug for SecretString {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("SecretString([REDACTED])")
    }
}

impl FromStr for SecretString {
    type Err = String;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        Ok(Self::new(value))
    }
}

impl Serialize for SecretString {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str("[REDACTED]")
    }
}

impl JsonSchema for SecretString {
    fn schema_name() -> String {
        "SecretString".to_string()
    }

    fn json_schema(_gen: &mut SchemaGenerator) -> Schema {
        let mut object = SchemaObject {
            instance_type: Some(SingleOrVec::Single(Box::new(InstanceType::String))),
            ..SchemaObject::default()
        };
        object.metadata = Some(Box::new(Metadata {
            description: Some("Secret string value. Redacted in Tooli output.".to_string()),
            ..Metadata::default()
        }));
        object.format = Some("password".to_string());
        Schema::Object(object)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn input_source_parses_stdin_and_files() {
        assert_eq!("-".parse::<InputSource>().unwrap(), InputSource::Stdin);
        assert_eq!(
            "notes.txt".parse::<InputSource>().unwrap(),
            InputSource::File(PathBuf::from("notes.txt"))
        );
        assert!("".parse::<InputSource>().is_err());
    }

    #[test]
    fn secret_string_redacts_debug_and_serialization() {
        let secret = SecretString::new("super-secret");

        assert_eq!(secret.expose_secret(), "super-secret");
        assert_eq!(format!("{secret:?}"), "SecretString([REDACTED])");
        assert_eq!(serde_json::to_value(&secret).unwrap(), json!("[REDACTED]"));
    }
}
