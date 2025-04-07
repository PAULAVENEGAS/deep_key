from openai import OpenAI

client=OpenAI(api_key="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",
              base_url="https://openrouter.ai/api/v1")


email_body = {
    """Hi there, pablo trucking LLC has been retained to monitor the insurance status of KEVIN'S
moreno TRANSPORT DBA (DOT #03723347, MC #1311448). Please provide a certificate of insurance (COI) for us to review and verify.

Action Required from Insurance Agency:
Send a single COI for KEVIN'S moreno TRANSPORT DBA to kevinhurt13@gmail.com.
Include all current insurance policies on the COI, including all the VINs on Scheduled Auto policies, as well as reefer breakdown or trailer interchange coverage with their limit amounts and deductibles. Please also include any General Liability policies, if available.

Add pablo trucking LLC as the Certificate Holder:
pablo trucking LLC  
5931 Greenville Ave, Unit #5620  
Dallas, TX 75206  

Add JORGE TRANSPORTATION INC. as the Certificate Holder too:
I NEED TO SEND THE INFORMATION TOO TO THE NEXT EMAIL jorge@intruckscorp.com  

pablo trucking LLC is a third-party insurance monitoring service verifying the insurance coverage of motor carriers in the industry. We have been engaged by several large freight brokers to obtain, review, and verify the certificates of insurance on their current carrier list so that we can monitor carrier insurance coverage.  

Please reply to this email or contact us at coi@pablo trucking LLC.com should you have any questions.  

Thanks,  
The pablo trucking LLC Team  

InTrucksCorp  
Login to begin managing the agency customers, fill ACORD forms, send out certificates by fax and email, track commissions and much more.  
intrucks.nowcerts.com  

Ref ID: 101970275"""
}


chat_cliente = client.chat.completions.create(
    model="deepseek/deepseek-r1-distill-llama-70b:free",
    messages=[
        {
            "role": "user",
            "content": f"Extract only the client name from the following text and respond only with the name: {email_body}"
        }
    ]
)


nombre_cliente=chat_cliente.choices[0].message.content
print(nombre_cliente)

chat_holder = client.chat.completions.create(
    model="deepseek/deepseek-r1-distill-llama-70b:free",
    messages=[
        {
            "role": "user",
            "content": f"Extract only the holder name from the following text and respond only with the name: {email_body}"
        }
    ]
)


nombre_holder=chat_holder.choices[0].message.content
print(nombre_holder)


