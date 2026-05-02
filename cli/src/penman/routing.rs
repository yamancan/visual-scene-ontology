//! Loads `tools/penman/routing-tables.json` at compile time.
//!
//! The JSON is the single source of truth for VSON-P -> Turtle role routing.
//! Embedding it via `include_str!` means the binary is self-contained and
//! cannot drift from the Python reference between builds.

use once_cell::sync::Lazy;
use serde::Deserialize;
use std::collections::{HashMap, HashSet};

const ROUTING_JSON: &str = include_str!("../../../tools/penman/routing-tables.json");

#[derive(Deserialize)]
struct Raw {
    namespaces: HashMap<String, String>,
    role_namespace_overrides: HashMap<String, String>,
    container_roles: Vec<String>,
    rcc_values: Vec<String>,
    role_value_to_vso: Vec<String>,
    role_value_to_rcc: Vec<String>,
    role_value_as_string: Vec<String>,
}

pub struct Routing {
    pub vso: String,
    pub allen: String,
    pub rcc: String,
    pub default: String,
    pub role_namespace_overrides: HashMap<String, String>,
    pub container_roles: HashSet<String>,
    pub rcc_values: HashSet<String>,
    pub role_value_to_vso: HashSet<String>,
    pub role_value_to_rcc: HashSet<String>,
    pub role_value_as_string: HashSet<String>,
}

pub static ROUTING: Lazy<Routing> = Lazy::new(|| {
    let raw: Raw = serde_json::from_str(ROUTING_JSON).expect("routing-tables.json malformed");
    let resolve = |key: &str| raw.namespaces.get(key).cloned().unwrap_or_default();
    let role_namespace_overrides = raw
        .role_namespace_overrides
        .iter()
        .map(|(role, ns_key)| (role.clone(), resolve(ns_key)))
        .collect();
    Routing {
        vso: resolve("vso"),
        allen: resolve("allen"),
        rcc: resolve("rcc"),
        default: resolve("default"),
        role_namespace_overrides,
        container_roles: raw.container_roles.into_iter().collect(),
        rcc_values: raw.rcc_values.into_iter().collect(),
        role_value_to_vso: raw.role_value_to_vso.into_iter().collect(),
        role_value_to_rcc: raw.role_value_to_rcc.into_iter().collect(),
        role_value_as_string: raw.role_value_as_string.into_iter().collect(),
    }
});
