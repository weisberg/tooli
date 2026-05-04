//! Internal helpers shared across the crate.

pub(crate) fn is_false(value: &bool) -> bool {
    !*value
}
