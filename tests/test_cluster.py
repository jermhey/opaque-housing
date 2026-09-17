import polars as pl

from opaque_housing.normalize.names import owner_key, primary_owner_name
from opaque_housing.resolve.cluster import cluster_members, component_sizes
from opaque_housing.resolve.denylist import address_denied, seed_agent_names
from opaque_housing.resolve.links import address_links, person_links


def test_union_find_connects_pairs_and_keeps_singletons() -> None:
    membership = cluster_members(["a", "b", "c", "d"], [("a", "b"), ("b", "c")])
    assert membership["a"] == membership["c"]
    assert membership["d"] == "d"
    sizes = component_sizes(membership, keep={"a", "b", "c", "d"})
    assert sorted(sizes.values()) == [1, 3]


def test_person_links_ignore_agents() -> None:
    contacts = pl.DataFrame(
        {
            "owner_key": ["aaa", "bbb", "ccc"],
            "person_key": ["p1", "p1", "p2"],
            "person_name_normalized": ["JANE DOE", "JANE DOE", "RILEY AGENT"],
            "is_o1_person": [True, True, False],
        }
    )
    links = person_links(contacts)
    assert links.height == 1
    assert set(links["link_type"].to_list()) == {"hpd_person"}


def test_address_links_deny_high_degree_and_seed_agent() -> None:
    seeds = seed_agent_names(["CORPORATION SERVICE COMPANY"])
    rows = pl.DataFrame(
        {
            "owner_key": ["a", "b", "c", "d", "e"],
            "address_key": ["u", "u", "s", "s", "s"],
            "address_normalized": [
                "10 SAMPLE ROAD BROOKLYN NY 11201",
                "10 SAMPLE ROAD BROOKLYN NY 11201",
                "251 LITTLE FALLS DRIVE WILMINGTON DE 19808",
                "251 LITTLE FALLS DRIVE WILMINGTON DE 19808",
                "251 LITTLE FALLS DRIVE WILMINGTON DE 19808",
            ],
            "process_name_normalized": [
                "EXAMPLE HOLDINGS LLC",
                "EXAMPLE MIXED LLC",
                "CORPORATION SERVICE COMPANY",
                "CORPORATION SERVICE COMPANY",
                "CORPORATION SERVICE COMPANY",
            ],
        }
    )
    links, denied = address_links(
        rows,
        owner_col="owner_key",
        address_key_col="address_key",
        address_col="address_normalized",
        agent_name_col="process_name_normalized",
        seeds=seeds,
        link_type="dos_process_address",
        threshold=3,
    )
    assert links.height == 1
    assert set(links["owner_key_a"].to_list() + links["owner_key_b"].to_list()) == {"a", "b"}
    assert "s" in denied["address_key"].to_list()
    assert address_denied(
        "251 LITTLE FALLS DRIVE WILMINGTON DE 19808",
        degree=3,
        agent_name_normalized="CORPORATION SERVICE COMPANY",
        seeds=seeds,
        threshold=3,
    )


def test_exact_name_skips_agent_corporation_hubs() -> None:
    from opaque_housing.opacity.build import build_graph

    parcels = pl.DataFrame(
        {
            "owner_key": ["aaa", "bbb"],
            "name_normalized": ["ONE LLC", "TWO LLC"],
            "owner_class": ["llc", "llc"],
        }
    )
    contacts = pl.DataFrame(
        {
            "owner_key": ["aaa", "bbb"],
            "type": ["Agent", "Agent"],
            "corporation_owner_key": ["mgmt", "mgmt"],
            "corporation_name_normalized": ["ACME MGMT LLC", "ACME MGMT LLC"],
            "is_o1_person": [False, False],
            "person_key": ["", ""],
            "person_name_normalized": ["", ""],
            "address_key": ["x", "y"],
            "address_normalized": ["1 MAIN ST", "2 MAIN ST"],
        }
    )
    links, _denied, membership = build_graph(
        parcels, contacts, parcels.head(0), seeds=frozenset(), threshold=20
    )
    assert links.filter(pl.col("link_type") == "exact_name").height == 0
    assert membership["aaa"] != membership["bbb"]


def test_owner_key_stable_for_fixture_names() -> None:
    assert owner_key(primary_owner_name("EXAMPLE HOLDINGS LLC"))
