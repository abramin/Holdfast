Feature: Event Catalog
  As a customer
  I want to browse and discover events
  So that I can find events to attend

  Scenario: List all events
    Given events exist in the catalog
    When a customer requests the event list
    Then they receive a paginated list of events

  Scenario: Get event details
    Given an event exists in the catalog
    When a customer requests the event details
    Then they receive the event details

  Scenario: Get event details for non-existent event
    When a customer requests details for a non-existent event
    Then they receive a 404 not found response

  Scenario: List sessions for an event
    Given an event with sessions exists
    When a customer requests the sessions for that event
    Then they receive a list of sessions with ticket types

  Scenario: Cached response for event list
    Given events exist in the catalog
    And the event list has been cached
    When a customer requests the event list
    Then they receive a cached response
