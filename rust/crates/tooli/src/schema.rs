//! JSON Schema generation for command input/output types.
//!
//! Schemars produces schemas with `$ref` indirection and a top-level
//! `definitions` block. Agents and skill consumers prefer inlined schemas, so
//! this module dereferences refs and strips `definitions` recursively. A
//! depth bound prevents infinite recursion on self-referential types — the
//! `$ref` is left intact once the bound is hit, which produces a still-valid
//! JSON Schema.

use crate::{Command, CommandMeta};
use serde::Serialize;
use serde_json::{json, Map, Value};

/// How deep we are willing to inline `$ref`s before bailing out and leaving
/// the reference in place. Recursive types (`struct Tree { children: Vec<Tree> }`)
/// otherwise expand without bound.
const MAX_REF_DEPTH: usize = 64;

/// Agent-facing schema for one command.
///
/// Field naming uses MCP-friendly camelCase (`inputSchema`, `outputSchema`,
/// `requiresConfirmation`, `deprecatedMessage`) to match the rest of the
/// schema/metadata surface; the envelope itself stays snake_case.
#[derive(Debug, Clone, Serialize)]
pub struct CommandSchema {
    pub name: String,
    pub description: String,
    #[serde(rename = "inputSchema")]
    pub input_schema: Value,
    #[serde(rename = "outputSchema", skip_serializing_if = "Option::is_none")]
    pub output_schema: Option<Value>,
    #[serde(default, skip_serializing_if = "crate::AnnotationSet::is_empty")]
    pub annotations: crate::AnnotationSet,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub capabilities: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub examples: Vec<crate::Example>,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub deprecated: bool,
    #[serde(rename = "deprecatedMessage", skip_serializing_if = "Option::is_none")]
    pub deprecated_message: Option<String>,
    #[serde(
        rename = "requiresConfirmation",
        default,
        skip_serializing_if = "std::ops::Not::not"
    )]
    pub requires_confirmation: bool,
}

/// Generate a command schema using `schemars`.
pub fn command_schema<C: Command>(name: impl Into<String>) -> CommandSchema {
    let name = name.into();
    let meta = C::meta();
    command_schema_with_meta::<C>(name, meta)
}

fn command_schema_with_meta<C: Command>(name: String, meta: CommandMeta) -> CommandSchema {
    let input_schema = serde_json::to_value(schemars::schema_for!(C))
        .map(inline_refs)
        .unwrap_or_else(|_| json!({}));
    let output_schema = serde_json::to_value(schemars::schema_for!(<C as Command>::Output))
        .map(inline_refs)
        .ok();

    CommandSchema {
        name,
        description: meta.description.unwrap_or_default(),
        input_schema,
        output_schema,
        annotations: meta.annotations,
        capabilities: meta.capabilities,
        examples: meta.examples,
        deprecated: meta.deprecated,
        deprecated_message: meta.deprecated_message,
        requires_confirmation: meta.requires_confirmation,
    }
}

/// Inline `$ref`s, strip `definitions`/`$defs`, and flatten single-element
/// `allOf` wrappers. Bounded by [`MAX_REF_DEPTH`] for cycle safety.
fn inline_refs(schema: Value) -> Value {
    let root = schema.clone();
    inline_value(schema, &root, 0)
}

fn inline_value(value: Value, root: &Value, depth: usize) -> Value {
    if depth > MAX_REF_DEPTH {
        return value;
    }
    match value {
        Value::Array(items) => Value::Array(
            items
                .into_iter()
                .map(|item| inline_value(item, root, depth))
                .collect(),
        ),
        Value::Object(mut object) => {
            if let Some(reference) = object.get("$ref").and_then(Value::as_str) {
                if let Some(resolved) = resolve_local_ref(reference, root) {
                    return inline_value(resolved, root, depth + 1);
                }
            }

            object.remove("definitions");
            object.remove("$defs");

            let mut next = Map::new();
            for (key, child) in object {
                next.insert(key, inline_value(child, root, depth));
            }
            if let Some(flattened) = flatten_single_all_of(&mut next) {
                return Value::Object(flattened);
            }
            Value::Object(next)
        }
        other => other,
    }
}

fn flatten_single_all_of(object: &mut Map<String, Value>) -> Option<Map<String, Value>> {
    let all_of = object.remove("allOf")?;
    let Value::Array(items) = all_of else {
        object.insert("allOf".to_string(), all_of);
        return None;
    };
    if items.len() != 1 {
        object.insert("allOf".to_string(), Value::Array(items));
        return None;
    }

    let mut items = items;
    let Value::Object(mut flattened) = items.remove(0) else {
        object.insert("allOf".to_string(), Value::Array(items));
        return None;
    };

    for (key, value) in std::mem::take(object) {
        flattened.insert(key, value);
    }
    Some(flattened)
}

fn resolve_local_ref(reference: &str, root: &Value) -> Option<Value> {
    let path = reference.strip_prefix('#')?;
    root.pointer(path).cloned()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Command, CommandMeta, Context, Result};
    use schemars::JsonSchema;
    use serde::Serialize;

    #[derive(JsonSchema)]
    struct Args;

    #[derive(Serialize, JsonSchema)]
    struct Row {
        value: String,
    }

    impl Command for Args {
        type Output = Vec<Row>;

        fn meta() -> CommandMeta {
            CommandMeta::new().description("test command")
        }

        fn run(self, _ctx: Context) -> Result<Self::Output> {
            Ok(Vec::new())
        }
    }

    #[derive(Serialize, JsonSchema)]
    struct Tree {
        value: String,
        children: Vec<Tree>,
    }

    #[derive(JsonSchema)]
    struct TreeArgs;

    impl Command for TreeArgs {
        type Output = Tree;

        fn run(self, _ctx: Context) -> Result<Self::Output> {
            Ok(Tree {
                value: String::new(),
                children: Vec::new(),
            })
        }
    }

    #[test]
    fn output_schema_inlines_local_refs() {
        let schema = command_schema::<Args>("rows");
        let rendered = serde_json::to_string(&schema.output_schema).unwrap();

        assert!(!rendered.contains("\"$ref\""));
        assert!(!rendered.contains("\"definitions\""));
    }

    #[test]
    fn schema_flattens_single_all_of_wrappers() {
        let raw = json!({
            "properties": {
                "source": {
                    "allOf": [{"type": "string"}],
                    "description": "File path"
                }
            }
        });
        let rendered = inline_refs(raw);

        assert_eq!(rendered["properties"]["source"]["type"], "string");
        assert_eq!(rendered["properties"]["source"]["description"], "File path");
        assert!(rendered["properties"]["source"].get("allOf").is_none());
    }

    #[test]
    fn recursive_schemas_terminate_with_remaining_ref() {
        // The recursion bound prevents infinite expansion. The result is still
        // valid JSON Schema — the $ref leaf at the depth limit stays intact.
        let schema = command_schema::<TreeArgs>("tree");
        let rendered =
            serde_json::to_string(&schema.output_schema).expect("schema should serialize");
        assert!(rendered.contains("\"value\""));
        assert!(rendered.contains("\"children\""));
    }
}
