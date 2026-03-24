# Two-Step Opt-Out Solution for Email Content

With the two-step opt-out solution, there are HTML pages for the confirmation action and a goodbye message. When a recipient clicks the unsubscribe link, they are directed to a *confirmation* page. On this page, they perform an action (such as clicking a link or a button) that confirms the decision to opt out. After that action, the recipient is redirected to a *goodbye page*, which informs them that they are unsubscribed.

The example that is provided is a confirmation page with custom JavaScript code.

## Prerequisites

This example requires knowledge of JavaScript and HTML.

## Using this Example

Open the HTML file and review the JavaScript code. When the customer clicks the confirmation button, these actions take place:

1. The JavaScript code populates the required variables from the query parameters in the initial URL. For more information
   about the query parameters, see [Two-Step Opt-Out with Customer-Branded Pages](https://documentation.sas.com/?cdcId=cintcdc&cdcVersion=production.a&docsetId=cintag&docsetTarget=p1k23bj83g45ukn1h4jxg3xno999.htm#p0ado9e2zfnlamn13d51twbeden6).
2. An opt-out request is sent to SAS Customer Intelligence 360.
3. The customer is directed to a goodbye page or the page is changed to display this content.

## Additional Resources

For more information about this process and other opt-out solutions, see these links:

* [Two-Step Opt-Out with Customer-Branded Pages](https://documentation.sas.com/?cdcId=cintcdc&cdcVersion=production.a&docsetId=cintag&docsetTarget=p1k23bj83g45ukn1h4jxg3xno999.htm#p0ado9e2zfnlamn13d51twbeden6)
* [Using a Two-Step Opt-Out Solution](https://documentation.sas.com/?cdcId=cintcdc&cdcVersion=production.a&docsetId=cintag&docsetTarget=p1k23bj83g45ukn1h4jxg3xno999.htm).
* [Use Unsubscribe Links for Opting Out](https://documentation.sas.com/?cdcId=cintcdc&cdcVersion=production.a&docsetId=cintag&docsetTarget=email-config-unsubscribe-by-link.htm)
