# rules/bidders.md - Actors, Groups, and Relations

## Actor Unit

The canonical actor can be an organization, person, group, vehicle, cohort, or
committee. The filing's bidding unit is preserved. A buyer group, club bid,
sponsor/corporate pair, or changing coalition can be one actor.

Member relations are composition facts. They do not automatically create
bidder rows or bid events.

## Bidder Class

Every actor claim includes `actor_class`: `financial`, `strategic`, `mixed`, or
`unknown`. Use `financial` for financial sponsors, private equity firms, and
financial-buyer cohorts. Use `strategic` for operating/corporate buyers and
strategic-buyer cohorts. Use `mixed` only when the filing supports a mixed
financial/strategic bidder, group, or cohort. Use `unknown` when the filing
does not support the class. Ignore U.S./non-U.S., public/private, and other
side descriptors.

## Relation Direction

- `member_of`: subject is the member; object is the group.
- `joins_group`: subject is the joining actor; object is the group.
- `exits_group`: subject is the exiting actor; object is the group.
- `affiliate_of`: subject is the affiliate; object is the related actor.
- `controls`: subject controls object.
- `acquisition_vehicle_of`: subject is the vehicle; object is parent/group.
- `advises`: subject is advisor; object is advised party.
- `finances`: subject provides financing/capital to object.
- `supports`: subject supports object/transaction.
- `voting_support_for`: subject is supporting holder/entity; object is buyer,
  agreement, proposal, or transaction.
- `rollover_holder_for`: subject is holder rolling/contributing/retaining
  equity; object is buyer, vehicle, surviving company, target, or transaction.

## Group Doctrine

Do not hard-atomize consortiums. A group bid remains a group bid unless the
filing shows a member separately acting as a bidder.

Member, support, financing, and rollover facts are `actor_relation_claims`, not
new bidder rows. Relation timing is source-backed; populate
`effective_date_first` only when the filing supports the timing.

Changing coalitions remain actor-cycle facts when the filing treats them
differently over time. Do not make membership permanent without quote support.

## Anonymous and Count-Only Actors

Use `cohort` with `observability=count_only` for generic counts that do not
identify bidder actors. Generic count phrases do not become named bidders.
Anonymous handles are deal-local and must be source-supported.
